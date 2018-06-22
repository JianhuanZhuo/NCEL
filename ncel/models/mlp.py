# -*- coding: utf-8 -*-
import numpy as np

# PyTorch
import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F

from ncel.utils.layers import Embed, to_gpu, MLPClassifier


def build_model(base_feature_dim, initial_embeddings, FLAGS):
    model_cls = MLPC
    layers_dim = [2000]
    use_contexts2 = FLAGS.use_lr_context
    use_att = FLAGS.att
    neighbor_window = 3
    return model_cls(
        base_feature_dim,
        initial_embeddings,
        layers_dim=layers_dim,
        mlp_ln=FLAGS.mlp_ln,
        dropout=FLAGS.dropout,
        fine_tune_loaded_embeddings=FLAGS.fine_tune_loaded_embeddings,
        use_contexts2=use_contexts2,
        use_att=use_att,
        neighbor_window = neighbor_window
    )


class MLPC(nn.Module):

    def __init__(self,
                 base_dim,
                 initial_embeddings,
                 layers_dim=[],
                 mlp_ln=False,
                 dropout = 0.0,
                 fine_tune_loaded_embeddings=None,
                 use_contexts2=True,
                 use_att=True,
                 neighbor_window=3
                 ):
        super(MLPC, self).__init__()

        self._use_contexts2 = use_contexts2
        self._use_att = use_att
        self._dropout_rate = dropout
        self._neighbor_window = neighbor_window

        word_embeddings, entity_embeddings, sense_embeddings, mu_embeddings = initial_embeddings
        word_vocab_size, word_embedding_dim = word_embeddings.shape
        entity_vocab_size, entity_embedding_dim = entity_embeddings.shape
        self._has_sense = True if sense_embeddings is not None else False
        if self._has_sense:
            sense_vocab_size, sense_embedding_dim = sense_embeddings.shape
        self._dim = word_embedding_dim
        assert self._dim==entity_embedding_dim and not ( self._has_sense and self._dim!=sense_embedding_dim), "unmatched dim!"

        self.word_embed = Embed(self._dim, word_vocab_size,
                            vectors=word_embeddings, fine_tune=fine_tune_loaded_embeddings)

        self.entity_embed = Embed(self._dim, entity_vocab_size,
                            vectors=entity_embeddings, fine_tune=fine_tune_loaded_embeddings)

        if self._has_sense:
            self.sense_embed = Embed(self._dim, sense_vocab_size,
                                      vectors=sense_embeddings, fine_tune=fine_tune_loaded_embeddings)
            self.mu_embed = Embed(self._dim, sense_vocab_size,
                                    vectors=mu_embeddings, fine_tune=fine_tune_loaded_embeddings)

        self.embeds = [self.word_embed, self.entity_embed, self.sense_embed, self.mu_embed]

        # base_dim + sense_dim + word_dim + 2 + 1(if has entity) + (2+word_dim)(if has contexts) + 1(if has context2 and has entity)
        self._feature_dim = base_dim + 2 + 2*self._dim
        if self._has_sense:
            self._feature_dim += 4

        if self._use_contexts2:
            self._feature_dim += 1 + self._dim
            if self._has_sense:
                self._feature_dim += 2

        if self._neighbor_window>0:
            self._feature_dim += 1
            if self._has_sense:
                self._feature_dim += 2

        self.mlp_classifier = MLPClassifier(self._feature_dim, 1, layers_dim=layers_dim,
                                            mlp_ln=mlp_ln, dropout=dropout)
        self.reset_parameters()

    # types: index of [word,entity,sense,mu]
    def run_embed(self, x, type):
        embeds = self.embeds[type](x)
        embeds = F.dropout(embeds, self._dropout_rate, training=self.training)
        return embeds

    def getEmbFeatures(self, sents, q_emb=None):
        batch_size, cand_num, seq_length = sents.size()

        sents_emb = self.run_embed(sents, 0)
        sents_emb = sents_emb.view(batch_size * cand_num, seq_length, -1)

        if self._use_att and q_emb is not None:
            att = torch.bmm(q_emb.unsqueeze(1), sents_emb.transpose(1, 2))
            f_emb = torch.bmm(att, sents_emb).squeeze()
        else:
            f_emb = torch.mean(sents_emb, dim=1)

        return f_emb

    def leftMvNeigh(self, emb, mv_steps, margin_col, mask):
        left_neigh_emb = torch.cat([margin_col, emb[:-mv_steps,:]], dim=0)
        left_neigh_emb = left_neigh_emb * mask
        return left_neigh_emb

    def rightMvNeigh(self, emb, mv_steps, margin_col, mask):
        right_neigh_emb = torch.cat([emb[mv_steps:,:], margin_col], dim=0)
        right_neigh_emb = right_neigh_emb * mask
        return right_neigh_emb

    # emb : (batch * cand_num) * dim
    # mask: (batch * cand_num) * dim
    def getNeighEmb(self, mstr_emb, cand_num, neighbor_window, left_mask, right_mask):
        margin_col = to_gpu(Variable(torch.zeros(cand_num, self._dim), requires_grad=False))
        # left_neighs: (batch_size*cand_num) * window * dim
        tmp_left_neigh_list = []
        tmp_left_neigh_list.append(self.leftMvNeigh(mstr_emb, cand_num, margin_col, left_mask))
        for i in range(neighbor_window-1):
            tmp_left_neigh_list.append(self.leftMvNeigh(tmp_left_neigh_list[i], cand_num, margin_col, left_mask))
        for i, neigh in enumerate(tmp_left_neigh_list):
            tmp_left_neigh_list[i] = tmp_left_neigh_list[i].unsqueeze(1)
        left_neighs = torch.cat(tmp_left_neigh_list, dim=1)

        tmp_right_neigh_list = []
        tmp_right_neigh_list.append(self.rightMvNeigh(mstr_emb, cand_num, margin_col, right_mask))
        for i in range(neighbor_window - 1):
            tmp_right_neigh_list.append(self.rightMvNeigh(tmp_right_neigh_list[i], cand_num, margin_col, right_mask))
        for i, neigh in enumerate(tmp_right_neigh_list):
            tmp_right_neigh_list[i] = tmp_right_neigh_list[i].unsqueeze(1)
        right_neighs = torch.cat(tmp_right_neigh_list, dim=1)
        # neigh_emb: (batch_size*cand_num) * 2window * dim
        neigh_emb = torch.cat((left_neighs, right_neighs), dim=1)
        # neigh_emb: (batch_size*cand_num) * dim
        neigh_emb = torch.mean(neigh_emb, dim=1)
        return neigh_emb

    # contexts1 : batch * candidate * tokens
    # contexts2 : batch * candidate * tokens
    # base_feature : batch * candidate * features, numpy
    # candidates : batch * candidate
    # candidates_entity: batch * candidate
    # length: batch
    # num_mentions: batch * cand
    def forward(self, contexts1, base_feature, candidates, m_strs,
                contexts2=None, candidates_sense=None, num_mentions=None, length=None):
        batch_size, cand_num, _ = base_feature.shape
        # to gpu
        base_feature = to_gpu(Variable(torch.from_numpy(base_feature))).float()
        contexts1 = to_gpu(Variable(torch.from_numpy(contexts1))).long()
        candidates = to_gpu(Variable(torch.from_numpy(candidates))).long()
        m_strs = to_gpu(Variable(torch.from_numpy(m_strs))).long()

        # candidate mask
        if length is not None:
            lengths_var = to_gpu(Variable(torch.from_numpy(length), requires_grad=False)).long()
            # batch_size * cand_num
            length_mask = sequence_mask(lengths_var, cand_num).float()
        # mention context mask
        has_neighbors = False
        if self._neighbor_window > 0 and num_mentions is not None:
            # batch * cand
            margin_col = to_gpu(Variable(torch.zeros(1, cand_num), requires_grad=False))
            right_neigh_mask = to_gpu(Variable(torch.from_numpy(num_mentions), requires_grad=False)).float()
            left_neigh_mask = torch.cat([margin_col, right_neigh_mask[:-1,:]], dim=0)
            right_neigh_mask_expand = right_neigh_mask.view(-1).unsqueeze(1).expand(batch_size*cand_num, self._dim)
            left_neigh_mask_expand = left_neigh_mask.view(-1).unsqueeze(1).expand(batch_size*cand_num, self._dim)
            has_neighbors = True

        has_context2 = False
        if contexts2 is not None and self._use_contexts2:
            contexts2 = to_gpu(Variable(torch.from_numpy(contexts2))).long()
            has_context2 = True

        has_sense = False
        if candidates_sense is not None and self._has_sense:
            candidates_sense = to_gpu(Variable(torch.from_numpy(candidates_sense))).long()
            has_sense = True

        # get emb, (batch * cand) * dim
        cand_entity_emb = self.run_embed(candidates, 1)
        f1_entity_emb = self.getEmbFeatures(contexts1, q_emb=cand_entity_emb)

        if has_sense:
            cand_sense_emb = self.run_embed(candidates_sense, 2)
            cand_mu_emb = self.run_embed(candidates_sense, 3)
            f1_sense_emb = self.getEmbFeatures(contexts1, q_emb=cand_sense_emb)
            f1_mu_emb = self.getEmbFeatures(contexts1, q_emb=cand_mu_emb)

        if has_context2:
            f2_entity_emb = self.getEmbFeatures(contexts2, q_emb=cand_entity_emb)
            if has_sense:
                f2_sense_emb = self.getEmbFeatures(contexts2, q_emb=cand_sense_emb)
                f2_mu_emb = self.getEmbFeatures(contexts2, q_emb=cand_mu_emb)

        # get contextual similarity, (batch * cand) * contextual_sim
        cand_entity_emb_expand = cand_entity_emb.unsqueeze(1)
        if has_sense:
            cand_sense_emb_expand = cand_sense_emb.unsqueeze(1)
            cand_mu_emb_expand = cand_mu_emb.unsqueeze(1)

        # get mention string similarity
        ms_entity_emb = self.getEmbFeatures(m_strs, q_emb=cand_entity_emb)
        if has_sense:
            ms_sense_emb = self.getEmbFeatures(m_strs, q_emb=cand_sense_emb)
            ms_mu_emb = self.getEmbFeatures(m_strs, q_emb=cand_mu_emb)

        m_sim1 = torch.bmm(cand_entity_emb_expand, ms_entity_emb.unsqueeze(2)).squeeze(2)
        if has_sense:
            m_sim2 = torch.bmm(cand_sense_emb_expand, ms_sense_emb.unsqueeze(2)).squeeze(2)
            m_sim3 = torch.bmm(cand_mu_emb_expand, ms_mu_emb.unsqueeze(2)).squeeze(2)

        if has_neighbors:
            # (batch * cand_num) * dim
            neigh_entity_emb = self.getNeighEmb(ms_entity_emb, cand_num, self._neighbor_window, left_neigh_mask_expand, right_neigh_mask_expand)
            n_sim1 = torch.bmm(cand_entity_emb_expand, neigh_entity_emb.unsqueeze(2)).squeeze(2)
            if has_sense:
                neigh_sense_emb = self.getNeighEmb(ms_sense_emb, cand_num, self._neighbor_window, left_neigh_mask_expand, right_neigh_mask_expand)
                n_sim2 = torch.bmm(cand_sense_emb_expand, neigh_sense_emb.unsqueeze(2)).squeeze(2)
                neigh_mu_emb = self.getNeighEmb(ms_mu_emb, cand_num, self._neighbor_window, left_neigh_mask_expand, right_neigh_mask_expand)
                n_sim3 = torch.bmm(cand_mu_emb_expand, neigh_mu_emb.unsqueeze(2)).squeeze(2)

        # entity: context1
        sim1 = torch.bmm(cand_entity_emb_expand, f1_entity_emb.unsqueeze(2)).squeeze(2)
        if has_sense:
            # sense : context1
            sim2 = torch.bmm(cand_sense_emb_expand, f1_sense_emb.unsqueeze(2)).squeeze(2)
            # mu : context1
            sim3 = torch.bmm(cand_mu_emb_expand, f1_mu_emb.unsqueeze(2)).squeeze(2)


        # entity: context2
        if has_context2:
            sim4 = torch.bmm(cand_entity_emb_expand, f2_entity_emb.unsqueeze(2)).squeeze(2)
            if has_sense:
                # sense : context2
                sim5 = torch.bmm(cand_sense_emb_expand, f2_sense_emb.unsqueeze(2)).squeeze(2)
                # mu : context2
                sim6 = torch.bmm(cand_mu_emb_expand, f2_mu_emb.unsqueeze(2)).squeeze(2)

        # feature vec : batch * cand * feature_dim
        # feature dim: base_dim + 2*dim + 2 + 1(if has entity) +
        # (2+word_dim)(if has contexts) + 1(if has context2 and has entity)
        base_feature = base_feature.view(batch_size * cand_num, -1)
        h = torch.cat((base_feature, cand_entity_emb, f1_entity_emb, sim1, m_sim1), dim=1)
        if has_sense:
            h = torch.cat((h, sim2, sim3, m_sim2, m_sim3), dim=1)

        if has_context2:
            h = torch.cat((h, sim4, f2_entity_emb), dim=1)
            if has_sense:
                h = torch.cat((h, sim5, sim6), dim=1)
        if has_neighbors:
            h = torch.cat((h, n_sim1), dim=1)
            if has_sense:
                h = torch.cat((h, n_sim2, n_sim3), dim=1)

        h = self.mlp_classifier(h, length=length_mask.view(-1))
        # reshape, batch_size * cand_num
        h = h.view(batch_size, -1)

        output = masked_softmax(h, mask=length_mask)
        return output

    def reset_parameters(self):
        self.mlp_classifier.reset_parameters()


# length: batch_size
def sequence_mask(sequence_length, max_length):
    batch_size = sequence_length.size()[0]
    seq_range = torch.arange(0, max_length).long()
    seq_range_expand = seq_range.unsqueeze(0).expand(batch_size, max_length)
    seq_range_expand = Variable(seq_range_expand)
    if sequence_length.is_cuda:
        seq_range_expand = seq_range_expand.cuda()
    seq_length_expand = sequence_length.unsqueeze(1)
    return seq_range_expand < seq_length_expand

# batch * cand_num
def masked_softmax(logits, mask=None):
    if mask is not None:
        logits = logits * mask
    probs = F.softmax(logits, dim=1)
    return probs