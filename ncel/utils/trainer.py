# -*- coding: utf-8 -*-
import torch
import torch.optim as optim
from ncel.utils.layers import the_gpu
import os
from ncel.utils.misc import recursively_set_device

def get_checkpoint_path(FLAGS, suffix=".ckpt", best=False):
    # Set checkpoint path.
    if FLAGS.ckpt_path.endswith(".ckpt") or FLAGS.ckpt_path.endswith(".ckpt_best"):
        checkpoint_path = FLAGS.ckpt_path
    else:
        checkpoint_path = os.path.join(FLAGS.ckpt_path, FLAGS.experiment_name + suffix)
    if best and not FLAGS.ckpt_path.endswith(".ckpt_best"):
        checkpoint_path += "_best"
    return checkpoint_path

check_rho = 1.0
class ModelTrainer(object):
    def __init__(self, model, logger, epoch_length, vocabulary, FLAGS):
        self.model = model
        self.logger = logger
        self.epoch_length = epoch_length
        self.word_vocab, self.entity_vocab, self.sense_vocab, self.id2wiki_vocab = vocabulary

        self.logger.Log('One epoch is ' + str(self.epoch_length) + ' steps.')

        self.dense_parameters = [param for name, param in model.named_parameters() if name
                                 not in ["word_embed.embed.weight", "entity_embed.embed.weight",
                                            "sense_embed.embed.weight", "mu_embed.embed.weight"]]
        self.sparse_parameters = [param for name, param in model.named_parameters() if name
                                  in ["word_embed.embed.weight", "entity_embed.embed.weight",
                                  "sense_embed.embed.weight", "mu_embed.embed.weight"]]
        self.optimizer_type = FLAGS.optimizer_type
        self.l2_lambda = FLAGS.l2_lambda
        self.ckpt_step = FLAGS.ckpt_step
        self.ckpt_on_best_dev_error = FLAGS.ckpt_on_best_dev_error
        self.learning_rate_decay_when_no_progress = FLAGS.learning_rate_decay_when_no_progress
        self.training_data_length = None
        self.eval_interval_steps = FLAGS.eval_interval_steps

        self.step = 0
        self.best_dev_step = 0

        # record best dev, test acc
        self.best_dev_mi_prec = 0
        self.best_dev_metrics = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        self.best_test_metrics = []

        # GPU support.
        self.gpu = FLAGS.gpu
        the_gpu.gpu = FLAGS.gpu
        if self.gpu >= 0:
            model.cuda()
        else:
            model.cpu()

        self.optimizer_reset(FLAGS.learning_rate)

        self.standard_checkpoint_path = get_checkpoint_path(FLAGS)
        self.best_checkpoint_path = get_checkpoint_path(FLAGS, best=True)

        # Load checkpoint if available.
        if FLAGS.load_best and os.path.isfile(self.best_checkpoint_path):
            self.logger.Log("Found best checkpoint, restoring.")
            self.load(self.best_checkpoint_path, cpu=FLAGS.gpu < 0)
            self.logger.Log(
                "Resuming at step: {} with best dev accuracy: {}".format(
                    self.step, self.best_dev_mi_prec))
        elif os.path.isfile(self.standard_checkpoint_path):
            self.logger.Log("Found checkpoint, restoring.")
            self.load(self.standard_checkpoint_path, cpu=FLAGS.gpu < 0)
            self.logger.Log(
                "Resuming at step: {} with best dev accuracy: {}".format(
                    self.step, self.best_dev_mi_prec))

    def reset(self):
        self.step = 0
        self.best_dev_step = 0

        # record best dev, test acc
        self.best_dev_mi_prec = 0
        self.best_dev_metrics = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        self.best_test_accs = []

    def optimizer_reset(self, learning_rate):
        self.learning_rate = learning_rate

        if self.optimizer_type == "Adam":
            self.optimizer = optim.Adam(self.dense_parameters, lr=learning_rate,
                weight_decay=self.l2_lambda)

            if len(self.sparse_parameters) > 0:
                self.sparse_optimizer = optim.SparseAdam(self.sparse_parameters, lr=learning_rate)
            else:
                self.sparse_optimizer = None
        elif self.optimizer_type == "SGD":
            self.optimizer = optim.SGD(self.dense_parameters, lr=learning_rate,
                weight_decay=self.l2_lambda)
            if len(self.sparse_parameters) > 0:
                self.sparse_optimizer = optim.SGD(self.sparse_parameters, lr=learning_rate)
            else:
                self.sparse_optimizer = None

    def optimizer_step(self):
        self.optimizer.step()
        if self.sparse_optimizer is not None:
            self.sparse_optimizer.step()
        self.step += 1

    def optimizer_zero_grad(self):
        self.optimizer.zero_grad()
        if self.sparse_optimizer is not None:
            self.sparse_optimizer.zero_grad()

    def new_accuracy(self, eval_metrics):
        # Track best dev error
        dev_metrics = eval_metrics[0]
        dev_mi_rec, dev_ma_rec, dev_mi_prec, dev_ma_prec, dev_mi_f1, dev_ma_f1 = dev_metrics
        if dev_mi_prec > check_rho * self.best_dev_mi_prec:
            self.best_dev_step = self.step
            if self.ckpt_on_best_dev_error and self.step > self.ckpt_step:
                self.logger.Log(
                    "Checkpointing with new best dev accuracy of %f" %
                    dev_mi_prec)
                self.save(self.best_checkpoint_path)
            self.best_dev_metrics = dev_metrics
            self.best_dev_mi_prec = dev_mi_prec
            if len(eval_metrics) > 1:
                self.best_test_metrics = eval_metrics[1:]

        # Learning rate decay
        if self.learning_rate_decay_when_no_progress != 1.0:
            last_epoch_start = self.step - (self.step % self.epoch_length)
            if self.step - last_epoch_start <= self.eval_interval_steps and self.best_dev_step < (last_epoch_start - self.epoch_length):
                    self.logger.Log('No improvement after one epoch. Lowering learning rate.')
                    self.optimizer_reset(self.learning_rate * self.learning_rate_decay_when_no_progress)

    def checkpoint(self):
        self.logger.Log("Checkpointing.")
        self.save(self.standard_checkpoint_path)

    def save(self, filename):
        if the_gpu() >= 0:
            recursively_set_device(self.model.state_dict(), gpu=-1)
            recursively_set_device(self.optimizer.state_dict(), gpu=-1)

        # Always sends Tensors to CPU.
        save_dict = {
            'step': self.step,
            'best_dev_step': self.best_dev_step,
            'best_dev_mi_prec': self.best_dev_mi_prec,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'word_vocab': self.word_vocab,
            'entity_vocab': self.entity_vocab,
            'sense_vocab': self.sense_vocab,
            'id2wiki_vocab': self.id2wiki_vocab
            }
        if self.sparse_optimizer is not None:
            save_dict['sparse_optimizer_state_dict'] = self.sparse_optimizer.state_dict()
        torch.save(save_dict, filename)

        if the_gpu() >= 0:
            recursively_set_device(self.model.state_dict(), gpu=the_gpu())
            recursively_set_device(self.optimizer.state_dict(), gpu=the_gpu())

    def load(self, filename, cpu=False):
        if cpu:
            # Load GPU-based checkpoints on CPU
            checkpoint = torch.load(
                filename, map_location=lambda storage, loc: storage)
        else:
            checkpoint = torch.load(filename)
        model_state_dict = checkpoint['model_state_dict']

        # restore words
        if 'word_embed.embed.weight' in model_state_dict:
            loaded_embeddings = model_state_dict['word_embed.embed.weight']
            del(model_state_dict['word_embed.embed.weight'])

            count = 0
            for word in checkpoint['word_vocab']:
                if word in self.word_vocab:
                    self_index = self.word_vocab[word]
                    loaded_index = checkpoint['word_vocab'][word]
                    self.model.word_embed.embed.weight.data[self_index, :] = loaded_embeddings[loaded_index, :]
                    count += 1
            self.logger.Log('Restored ' + str(count) + ' words from checkpoint.')

        # restore entities
        if 'entity_embed.embed.weight' in model_state_dict:
            loaded_embeddings = model_state_dict['entity_embed.embed.weight']
            del (model_state_dict['entity_embed.embed.weight'])

            count = 0
            for entity in checkpoint['entity_vocab']:
                if entity in self.entity_vocab:
                    self_index = self.entity_vocab[entity]
                    loaded_index = checkpoint['entity_vocab'][entity]
                    self.model.entity_embed.embed.weight.data[self_index, :] = loaded_embeddings[loaded_index, :]
                    count += 1
            self.logger.Log('Restored ' + str(count) + ' entities from checkpoint.')

        # restore senses and mu
        if 'sense_embed.embed.weight' in model_state_dict and 'mu_embed.embed.weight' in model_state_dict:
            loaded_sense_embeddings = model_state_dict['sense_embed.embed.weight']
            loaded_mu_embeddings = model_state_dict['mu_embed.embed.weight']
            del (model_state_dict['sense_embed.embed.weight'])
            del (model_state_dict['mu_embed.embed.weight'])

            count = 0
            for sense in checkpoint['sense_vocab']:
                if sense in self.sense_vocab:
                    self_index = self.sense_vocab[sense]
                    loaded_index = checkpoint['sense_vocab'][sense]
                    self.model.sense_embed.embed.weight.data[self_index, :] = loaded_sense_embeddings[loaded_index, :]
                    self.model.mu_embed.embed.weight.data[self_index, :] = loaded_mu_embeddings[loaded_index, :]
                    count += 1
            self.logger.Log('Restored ' + str(count) + ' senses from checkpoint.')

        self.model.load_state_dict(model_state_dict, strict=False)
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        if self.sparse_optimizer is not None:
            self.sparse_optimizer.load_state_dict(checkpoint['sparse_optimizer_state_dict'])

        self.step = checkpoint['step']
        self.best_dev_step = checkpoint['best_dev_step']
        self.best_dev_mi_prec = checkpoint['best_dev_mi_prec']
