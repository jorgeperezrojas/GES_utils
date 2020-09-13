import json
import re

from collections import defaultdict, Counter
from unidecode import unidecode
from simstring.feature_extractor.character_ngram import CharacterNgramFeatureExtractor
from simstring.feature_extractor.word_ngram import WordNgramFeatureExtractor
from simstring.feature_extractor.base import BaseFeatureExtractor
from simstring.measure.cosine import CosineMeasure
from simstring.database.dict import DictDatabase
from simstring.searcher import Searcher

import ipdb

class GESSimpleMatcher:
    '''
    Clase para hacer match simple de patologías GES. Solo considera similitud entre strings, 
    nada muy sofisticado. Basado en código de Fabián Villena (https://fabianvillena.cl).
    Actualmente considera un extractor de features que combina caracteres y palabras y tiene
    ciertas cosas específicas de textos GES.
    TODO: 
        - probar técnicas un poco más sofisticadas de matching
        - completar la documentación
    '''
    def __init__(
            self, 
            base_ges_data='ges_utils/data/ges-health-problems.json', 
            no_ges_str='UNK',
            alpha=0.2,
            n_chars=4, 
            n_words=[2], 
            special_words=['vih']
        ):

        self.alpha = alpha

        with open(base_ges_data,'r',encoding='utf-8') as f:
            self.__ges_dict = json.load(f)
        
        # feature extractor
        extractor = GESSyntacticFeatureExtractor(
                        n_chars=n_chars, 
                        n_words=n_words, 
                        special_words=special_words
                    )
        self.__db = DictDatabase(extractor)
        
        # Caché
        self.__cache = {}
        
        self.__problems_from_disease = defaultdict(set)
        self.__ids_from_disease = defaultdict(set)
        self.__problems = {}
        self.__ids = {}
        
        self.__problems[-1] = no_ges_str
        self.__ids[no_ges_str] = -1
        
        # Por ahora los ids son el orden de los problemas en el json
        # TODO: decidir si los ids deberían obtenerse de algún lugar estándar
        for i, problem in enumerate(self.__ges_dict):
            
            problem_id = i+1
            
            self.__problems[problem_id] = problem
            self.__ids[problem] = problem_id
            
            # agrega un problema como si fuera disease también
            self.__problems_from_disease[problem].add(problem)
            self.__ids_from_disease[problem].add(problem_id)
            
            # agrega a las BD 
            self.__db.add(problem)
            
            for disease in self.__ges_dict[problem]:
                
                self.__problems_from_disease[disease].add(problem)
                self.__ids_from_disease[disease].add(problem_id)
                
                # agrega a la BD
                self.__db.add(disease)
        
        # TODO: agregar datos adicionales para hacer matching de enfermedades y problemas

        self.__searcher = Searcher(self.__db, CosineMeasure())

    def get_ranking_ges_diseases(self, raw_string):
        ranking = self.__searcher.ranked_search(raw_string, alpha=self.alpha)
        return ranking

    def get_ges_problem(self, raw_string):
        problem_id = self.get_ges_id(raw_string)
        problem = self.__problems[problem_id]
        return problem        

    def get_ges_id(self, raw_string):
        # si ya lo computamos entrega el valor 
        if raw_string in self.__cache:
            return self.__cache[raw_string]
        
        # si no lo tenemos, lo computamos
        ranking = self.get_ranking_ges_diseases(raw_string)

        if ranking:
            # ipdb.set_trace()
            (v, disease) = ranking[0]
            problem_ids = self.__ids_from_disease[disease]
            problem_id = list(problem_ids)[0]
            self.__cache[raw_string] = problem_id
            return problem_id

        else:
            self.__cache[raw_string] = -1
            return -1


    def get_possible_ges_ids(self, raw_string):
        
        to_search = raw_string
        
        problem_ids = []
        
        # busca las enfermedades candidatas
        candidate_diseases = self.__searcher.search(to_search, alpha=self.alpha) 
        
        for disease in candidate_diseases:
            problem_ids.extend(self.__ids_from_disease[disease])
          
        problem_ids_counter = Counter(problem_ids)
        ordered_ids = [i for i,_ in problem_ids_counter.most_common()]
        
        return ordered_ids

    def get_ges_id_prev(self, raw_string):
        
        # si ya lo computamos entrega el valor 
        if hash(raw_string) in self.__cache:
            return self.__cache[hash(raw_string)]
        
        ids_list = self.get_possible_ges_ids(raw_string)
        if not ids_list:
            self.__cache[raw_string] = -1
            return -1
        else:
            self.__cache[raw_string] = ids_list[0]
            return ids_list[0]

    def problem_from_id(self, id_problem):
        return self.__problems[id_problem]

    def id_from_problem(self, problem):
        return self.__ids[problem]

    def clean_cache(self):
        self.__cache = {}


class GESSyntacticFeatureExtractor(BaseFeatureExtractor):
    def __init__(self, n_chars, n_words, special_words):
        self.n_chars = n_chars
        self.special_words = special_words
        self.__char_feature_extractor = CharacterNgramFeatureExtractor(n_chars)
        if type(n_words) != list:
            self.__word_feature_extractors = [WordNgramFeatureExtractor(n_words)]
        else:
            self.__word_feature_extractors = [
                WordNgramFeatureExtractor(n)
                for n in n_words
            ]

    def features(self, string):
        # lower y unicode
        normalized_string = string.lower()
        normalized_string = unidecode(normalized_string)
        
        # saca símbolos de puntuación
        normalized_string = re.sub(r'[,;()/+ -]+',' ',normalized_string)
        
        # elimina la información que no es necesaria (correspondiente a la edad)
        # 'en personas de'
        normalized_string = re.sub(r'en +personas +(de|desde)?',' ', normalized_string)
        # 'mayores de XX anos y mas'
        normalized_string = re.sub(r'(mayor(es)?( *de)?)? *\d+ +anos?( +y +mas)?', ' ', normalized_string)
        # 'desde XX anos y menores de XX anos' 'menores de XX anos'
        normalized_string = re.sub(r'(desde +\d+ +anos? +y)? *menores +de +\d+ +anos?', ' ', normalized_string)
        # 'de XX a XX anos'
        normalized_string = re.sub(r'de +\d+ a +\d+ anos?', ' ', normalized_string)
        
        # saca los ' y '
        normalized_string = re.sub(' y ', ' ', normalized_string)
        
        # saca los espacios de mas
        normalized_string = re.sub(' +', ' ', normalized_string)
        normalized_string = normalized_string.strip()
        
        # obtiene las características de caracteres
        char_features = self.__char_feature_extractor.features(normalized_string)
        
        # obtiene las características de palabras
        word_features = []
        for extractor in self.__word_feature_extractors:
            word_features += extractor.features(normalized_string)
            
        # obtiene características de palabras especiales
        special_features = []
        for word in self.special_words:
            re_word = f'(^{word})|( +{word} +)|({word}$)'
            if re.search(re_word, normalized_string):
                special_features.append(word)
        
        return char_features + word_features + special_features