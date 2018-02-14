CUDA_VISIBLE_DEVICES=5 python run_entity_linking.py --log_path /data/caoyx/log/ncel --training_data conll:2::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv --eval_data conll:0::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv,conll:1::/data/caoyx/el_datasets/AIDA-YAGO2-dataset.tsv --candidates_file ppr:/data/caoyx/el_datasets/ppr_candidate,wiki_title:/data/caoyx/el_datasets/vocab_entity.dat,wiki_anchor:/data/caoyx/el_datasets/entity_prior,wiki_redirect:/data/caoyx/el_datasets/redirect_candidate,dictionary:/data/caoyx/el_datasets/dictionary,yago:/data/caoyx/el_datasets/yagoLabels.ttl --wiki_entity_vocab /data/caoyx/el_datasets/vocab_entity.dat --word_embedding_file /data/caoyx/etc/eng_mpme/vectors_word1 --entity_embedding_file /data/caoyx/etc/eng_mpme/vectors_entity1 --sense_embedding_file /data/caoyx/etc/eng_mpme/vectors_sense1 --allow_cropping --seq_length 0 --doc_length 0 --max_candidates_per_document 200 --topn_candidate 0 --training_steps 10000 --learning_rate 0.01 --learning_rate_decay_when_no_progress 0.5 --dropout 0.0 --batch_size 5 --nofine_tune_loaded_embeddings --lowercase --noinclude_unresolved --noeval_only_mode --model_type NCEL --str_sim --prior --att --local_context_window 0 --global_context_window 5 --embedding_dim 200 --mlp_dim 400 --num_mlp_layers 0 --nomlp_ln --gpu 0 -gc_dim 300 --num_gc_layer 3 --nogc_ln --classifier_dim 300 --num_cm_layer 0 --nocm_ln --optimizer_type SGD --res_gc_layer_num 3 --xling 0.1 --early_stopping_steps_to_wait 10000 --support_fuzzy --save_candidates_path /data/caoyx/el_datasets/ncel_candidates --wiki_redirect_vocab /data/caoyx/el_datasets/redirect_id_vocab