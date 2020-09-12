import json

from collections import defaultdict, Counter
from unidecode import unidecode
from simstring.feature_extractor.character_ngram import CharacterNgramFeatureExtractor
from simstring.measure.cosine import CosineMeasure
from simstring.database.dict import DictDatabase
from simstring.searcher import Searcher

class GESSimpleMatcher:
    '''
    Clase para hacer match simple de patologías GES. Solo considera similitud entre strings, 
    nada muy sofisticado. Basado en código de Fabián Villena (https://fabianvillena.cl)
    TODO: completar la documentación
    '''
    def __init__(
            self, 
            base_ges_data='general_data/ges-health-problems.json', 
            no_ges_str='NO GES',
            alpha=0.65
        ):

        self.alpha = alpha

        with open(base_ges_data,'r',encoding='utf-8') as f:
            self.__ges_dict = json.load(f)
        
        # TODO: decidir si estas son las mejores características
        self.__db = DictDatabase(CharacterNgramFeatureExtractor(2))
        
        # Caché
        self.__cache = {}
        
        self.__problems_from_disease = defaultdict(list)
        self.__ids_from_disease = defaultdict(list)
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
            
            normalized_problem = self.__normalize(problem)
            
            # agrega un problema como si fuera disease también
            self.__problems_from_disease[normalized_problem].append(problem)
            self.__ids_from_disease[normalized_problem].append(problem_id)
            
            # agrega a las BD 
            self.__db.add(normalized_problem)
            
            for disease in self.__ges_dict[problem]:
                
                normalized_disease = self.__normalize(disease)
                
                self.__problems_from_disease[normalized_disease].append(problem)
                self.__ids_from_disease[normalized_disease].append(problem_id)
                
                # agrega a la BD
                self.__db.add(normalized_disease)
        
        self.__searcher = Searcher(self.__db, CosineMeasure())

    def __normalize(self, in_string):
        out_string = in_string.lower()
        out_string = unidecode(out_string)
        return out_string

    # se puede mover el alpha para ajustar la precisión
    def get_possible_ges_ids(self, raw_string):
        
        to_search = self.__normalize(raw_string)
        
        problem_ids = []
        
        # busca las enfermedades candidatas
        candidate_diseases = self.__searcher.search(to_search, alpha=self.alpha) 
        
        for disease in candidate_diseases:
            problem_ids.extend(self.__ids_from_disease[disease])
          
        problem_ids_counter = Counter(problem_ids)
        ordered_ids = [i for i,_ in problem_ids_counter.most_common()]
        
        return ordered_ids

    def get_ges_id(self, raw_string):
        
        # si ya lo computamos entrega el valor 
        if raw_string in self.__cache:
            return self.__cache[raw_string]
        
        ids_list = self.get_possible_ges_ids(raw_string)
        if not ids_list:
            self.__cache[raw_string] = -1
            return -1
        else:
            self.__cache[raw_string] = ids_list[0]
            return ids_list[0]

    def get_ges_problem(self, raw_string):
        problem_id = self.get_ges_id(raw_string)
        problem = self.__problems[problem_id]
        return problem

    def problem_from_id(self, id_problem):
        return self.__problems[id_problem]

    def id_from_problem(self, problem):
        return self.__ids[problem]

    def clean_cache(self):
        self.__cache = {}