CUDA_VISIBLE_DEVICES=5 python run_entity_linking.py --log_path /data/caoyx/log/ncel --training_data conll:2::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv --eval_data conll:0::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv,conll:1::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv --candidates_file /data/caoyx/el_datasets/ppr_candidate,/data/caoyx/el_datasets/wiki_candidate --entity_prior_file /data/caoyx/el_datasets/entity_prior --wiki_entity_vocab /data/caoyx/el_datasets/vocab_entity.dat --word_embedding_file /data/caoyx/etc/eng_mpme/vectors_word1 --entity_embedding_file /data/caoyx/etc/eng_mpme/vectors_entity1 --sense_embedding_file /data/caoyx/etc/eng_mpme/vectors_sense1 --yamada_model_file /data/caoyx/etc/yamada_vec/vectors_word0,/data/caoyx/etc/yamada_vec/vectors_entity0,/data/caoyx/etc/yamada_vec/vectors_weight.npy,/data/caoyx/etc/yamada_vec/vectors_bias.npy --allow_cropping --seq_length 200 --doc_length 100 --max_candidates_per_document 200 --topn_candidate 0 --training_steps 10000 --learning_rate 0.1 --learning_rate_decay_when_no_progress 0.5 --dropout 0.0 --batch_size 5 --nofine_tune_loaded_embeddings --lowercase --noinclude_unresolved --noeval_only_mode --model_type NCEL --str_sim --prior --att --local_context_window 0 --global_context_window 0 --embedding_dim 200 --mlp_dim 400 --num_mlp_layers 0 --nomlp_ln --gpu 0 -gc_dim 200 --num_gc_layer 3 --nogc_ln --classifier_dim 200 --num_cm_layer 0 --nocm_ln --optimizer_type SGD --res_gc_layer_num 3 --xling 0.1 --early_stopping_steps_to_wait 10000