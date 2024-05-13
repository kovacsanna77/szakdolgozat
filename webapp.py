# -*- coding: utf-8 -*-
"""webapp.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1cwBDCCZhtgjcOkeNQSqb-LoDSwDDOo2b
"""

#!pip install streamlit

import streamlit as st
import torch
from transformers import BertTokenizer
from torch.utils.data import TensorDataset, DataLoader, SequentialSampler
import torch.nn as nn
import joblib
import json
import pickle
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from bs4 import BeautifulSoup
import re
import itertools
from nltk.tokenize import word_tokenize
import numpy as np
import pandas as pd
import os
from tensorflow.keras.models import model_from_json, Sequential
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import sequence 
from tensorflow.keras.initializers import Orthogonal
from tensorflow.keras.initializers import Constant
from tensorflow.keras.layers import ReLU, Dropout, Bidirectional, LSTM, Embedding, Dense
from tensorflow.keras.losses import BinaryCrossentropy
from tensorflow.keras.optimizers import SGD
from transformers import AutoTokenizer
from transformers import BertModel
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('punkt', quiet=True)
tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')

def clean_reviews(review):

    # 1. Removing html tags
    review_text = BeautifulSoup(review,"lxml").get_text()

    # 2. Retaining only alphabets.
    review_text = re.sub("[^a-zA-Z]"," ",review_text)

    # 3. Converting to lower case and splitting
    word_tokens= review_text.lower().split()

    # 4. Remove stopwords
    le=WordNetLemmatizer()
    stop_words= set(stopwords.words("english"))
    word_tokens= [le.lemmatize(w) for w in word_tokens if not w in stop_words]

    cleaned_review=" ".join(word_tokens)
    return cleaned_review


base_dir = 'model.h5'
tokenizer_path = 'tokenizer.pkl'
# Check if the file exists
if not os.path.exists(tokenizer_path):
    raise FileNotFoundError(f"Tokenizer file not found at path: {tokenizer_path}")

try:
    # Load the tokenizer
    tok = joblib.load(tokenizer_path)
    print("Tokenizer loaded successfully.")
except Exception as e:
    print(f"An error occurred while loading the tokenizer: {e}")

# Load the configuration
config_path = 'config.json'
if not os.path.exists(config_path):
    raise FileNotFoundError(f"Config file not found at path: {config_path}")

try:
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
    print("Config loaded successfully.")
except Exception as e:
    print(f"An error occurred while loading the config: {e}")



   
#base_dir = 'model.h5'
#model = load_model(base_dir, custom_objects=custom_objects)
def pred_lstm(text):
       # Extract max_rev_len
    max_rev_len = config['max_rev_len']
    # Load the embedding matrix
    embed_matrix = np.load('embed_matrix.npy')
    
    # Load the model architecture
    with open('model.json', 'r') as json_file:
        model_json = json_file.read()
    
    # Reconstruct the model
    vocab_size = embed_matrix.shape[0]
    embed_dim = embed_matrix.shape[1]
    
    
    # Reconstruct the model
    model=Sequential()
    model.add(Embedding(input_dim=vocab_size, output_dim=embed_dim,
                        input_length=max_rev_len, weights=[embed_matrix],
                        trainable=True))
    model.add(Bidirectional(LSTM(64, dropout = 0.2)))
    model.add(Dense(64, activation = 'relu'))
    model.add(Dropout(0.1))
    model.add(Dense(1, activation='sigmoid'))
    
    # compile the model
    model.compile(optimizer= SGD(), loss=BinaryCrossentropy(), metrics=['accuracy'])
    
    # Load the model weights
    model.load_weights('model_weights.h5')
    sentences = tokenizer.tokenize(text.strip())
    cleaned_sentences = [clean_reviews(sent).split() for sent in sentences]
    sequences = tok.texts_to_sequences(cleaned_sentences)
    flattened_sequence = list(itertools.chain(*sequences))
    padded_sequences = pad_sequences([flattened_sequence], maxlen=max_rev_len, padding='post')
    predictions = model.predict(padded_sequences)
    predicted_class = (predictions > 0.5).astype(int)  
    
    return predicted_class[0]



class BERT_LSTM_Arch(nn.Module):
    def __init__(self, bert):
        super(BERT_LSTM_Arch, self).__init__()
        self.bert = bert

        # LSTM layer
        self.lstm = nn.LSTM(input_size=768, hidden_size=256, num_layers=1, batch_first=True, bidirectional=True)

        # Dropout layer
        self.dropout = nn.Dropout(0.25)

        # Relu activation function
        self.relu = nn.ReLU()
        self.sigmoid= nn.Sigmoid()
        self.fc2 = nn.Linear(512, 256)
        # Fully connected layer
        self.fc = nn.Linear(256, 2)

    def forward(self, sent_id, mask):
        # Passing the inputs to the model
        outputs = self.bert(sent_id, attention_mask=mask, return_dict=True)
        sequence_output = outputs.last_hidden_state

        # LSTM over the sequence
        lstm_output, (hidden, cell) = self.lstm(sequence_output)

        # Using the hidden state of the last time step
        lstm_output = torch.cat((hidden[-2,:,:], hidden[-1,:,:]), dim=1)

        x = self.fc2(lstm_output)
        x = self.relu(x)
        x = self.dropout(x)

        x = self.fc(x)
        x = self.sigmoid(x)

        return x


# Load a pretrained BERT model
bert = BertModel.from_pretrained("bert-base-uncased")

save_directory = 'bert'
tokenizerbert = AutoTokenizer.from_pretrained(save_directory)

model2_path = 'saved_weights_lstm.pt' #os.path.join(save_directory, 'saved_weights_lstm.pt')
model_bert = BERT_LSTM_Arch(bert)  # Initialize the model with the same architecture

# Load the model weights
model_bert.load_state_dict(torch.load(model2_path))
model_bert.eval()



def pred_bert(text):
    encoded_input = tokenizerbert.encode_plus(
            text,
            add_special_tokens=True,  # Add '[CLS]' and '[SEP]'
            return_attention_mask=True,
            padding='max_length',     # Pad to a length specified by the max_length
            truncation=True,
            max_length=512,           # Truncate or pad to a max_length specified by the model used
            return_tensors='pt'       # Return PyTorch tensors
        )

    input_ids = encoded_input['input_ids']
    attention_mask = encoded_input['attention_mask']

    # Move tensors to the same device as the model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_bert.to(device)
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    # Make prediction
    with torch.no_grad():
        outputs = model_bert(input_ids, attention_mask)
        predictions = torch.argmax(outputs, dim=1)

    predicted_class = predictions.cpu().numpy()[0]

    return predicted_class

#B = "Tensions soared as Biden threatened to withhold toy shipments to Israel's sandcastles if they dared storm Rafah. Israeli bigwigs flailed, Erdan wailed about emboldened foes, while Netanyahu flexed with a we'll stand alone video montage. Bidens jab rocked Israels war boat, prompting cries of Not fair! from Likuds Zohar and a Hamas loves Biden diss from Ben Gvir, causing Herzog to roll his eyes. Lapid finger-pointed at Netanyahu, warning of IDF soldier jeopardy, while Michaeli accused the government of turning Israel into a strategic sitting duck."
#A = "Israeli officials are reeling after US President Joe Biden's declaration that the US would cease some arms shipments if Israel launched a full-scale operation in Rafah. The statement, made in an interview with CNN, ignited criticism from Israeli Ambassador Gilad Erdan, who deemed it potentially emboldening to Israel's enemies. Prime Minister Benjamin Netanyahu responded by affirming Israel's resolve. Biden's stance underscores a shift in US-Israel relations amidst mounting pressure to protect Gazan civilians. Despite pleas to reconsider military plans, Israel has undertaken limited operations. Biden's move has stoked anger among Israeli politicians, exposing deep rifts. Likud Minister Miki Zohar decried forgetting past terror attacks, while Minister of National Security Itamar Ben Gvir's critique prompted President Isaac Herzog's rebuke. "


#print(pred_bert(A))

def predict_label(text, model_choice):
    if model_choice == 'BiLSTM':
        return pred_lstm(text)
    elif model_choice == 'BERT':
        return pred_bert(text)
    else:
        raise ValueError(f"Unknown model choice: {model_choice}")

if __name__ == '__main__':
    st.title("Fake news detection")
    models = ['BERT']
    chosen_model = st.selectbox('Choose a model', models)
    text = st.text_input('Enter text for prediction')

    if st.button('Predict'):
        result = predict_label(text, chosen_model)
        st.success(f"Prediction: {'True' if result == 1 else 'False'}")

  
