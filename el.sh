CUDA_VISIBLE_DEVICES=5 python run_entity_linking.py --log_path /data/caoyx/log/ncel --data_type aquaint --eval_text_path /data/caoyx/el_datasets/WNED/wned-datasets/aquaint/RawText/ --eval_mention_file /data/caoyx/el_datasets/WNED/wned-datasets/aquaint/aquaint.xml --candidates_file /data/caoyx/el_datasets/wiki_candidate --entity_prior_file /data/caoyx/el_datasets/entity_prior --wiki_entity_vocab /data/caoyx/el_datasets/vocab_entity.dat --word_embedding_file /data/caoyx/etc/exp1/envec/vectors_word0 --entity_embedding_file /data/caoyx/etc/exp1/envec/vectors_entity0 --sense_embedding_file /data/caoyx/etc/exp1/envec/vectors_sense0 --allow_cropping --seq_length 200 --doc_length 100 --max_candidates_per_document 400 --topn_candidate 20 --training_steps 10000 --learning_rate 0.5 --learning_rate_decay_when_no_progress 0.5 --dropout 0.0 --batch_size 5 --nofine_tune_loaded_embeddings --lowercase --noinclude_unresolved --noeval_only_mode --cross_validation 8 --model_type NCEL --str_sim --prior --att --local_context_window 0 --global_context_window 0 --embedding_dim 200 --mlp_dim 400 --num_mlp_layers 1 --nomlp_ln --gpu 0 -gc_dim 300 --num_gc_layer 2 --nogc_ln --classifier_dim 200 --num_cm_layer 1 --nocm_ln