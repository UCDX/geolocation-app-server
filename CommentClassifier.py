from transformers import BertTokenizer, BertForSequenceClassification
import torch
from transformers import pipeline

class Classifier() :

    def __init__(self):
        self.model_name = 'bert-base-uncased'
        self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
        self.model = BertForSequenceClassification.from_pretrained(self.model_name)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.classifier = pipeline('sentiment-analysis', model='nlptown/bert-base-multilingual-uncased-sentiment')

    def classifyComment(self,comment):
        sentiment=self.classifier(comment) # clasifica el comentario
        label=sentiment[0]['label'] # obtiene la etiqueta
        rate=int(label[0]) # Convierte el primer caracter en numero ya que devuelve "5 stars"
        return rate