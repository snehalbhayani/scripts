from flask import Flask,jsonify
import re
import sys
sys.path.append('./')
import models
import traceback
import nltk
from nltk.tag import pos_tag
from nltk.util import ngrams
import rethinkdb as r
from rethinkdb import RqlRuntimeError
from nltk.corpus import wordnet as wn 
from py2neo import Node, Relationship, Graph
from pywsd.similarity import max_similarity as maxsim
from pywsd import disambiguate
import pickle
from stanford_parser.parser import Parser  
from py2neo.server import GraphServer
app = Flask(__name__)
NEO4J_SERVER_DIST_PATH='/home/snehal/Downloads/neo4j-community-2.2.3/'

@app.route("/find_tags/<sentence>")
def tag(sentence):
    try:
        tags=nltk.pos_tag(nltk.word_tokenize(sentence))
    except:
        print(traceback.format_exc())
    return jsonify(tags)


def on_starting(server):
    print("Starting the server "+__name__)

@app.route("/find_similar_words/<word>/<corpus_to_use>",methods=['GET'])
def findsimilar(word,corpus_to_use):
    package = "nltk.corpus"
    name =str(corpus_to_use)
    try:
        imported = getattr(__import__(package, fromlist=[name]), name)
        #if name not in findsimilar.text.keys():
        print("looking for the corpus "+str(imported))
        stext = nltk.Text(word.lower() for word in imported.words())
        #else:
        #    print(name+" already found")
        stext.similar(word)
        similar_words = {'similar words':stext._word_context_index.similar_words(word)}
    except:
        print(traceback.format_exc())
    return jsonify(similar_words)
# We use a static text variable. This variable is a list of lower case words, extracted from a corpus.
findsimilar.text={}

@app.route("/find_synonyms/<word>",methods=['GET'])
def findsynonyms(word):
    sense_net={}
    try:
        synsets=wn.synsets(word)
        for synnet in synsets:
            if synnet.name().split('.')[0] not in sense_net:
                synnet[synnet.name().split('.')[0]]=[]
                synnet[synnet.name().split('.')[0]].extend(list(set(synnet.lemma_names())))
        print(str(synnet))
    except:
        print(traceback.format_exc())
    return jsonify(synnet)


@app.route("/enter",methods=['GET'])
def extract():
    try :
        r=models.extract(app)
    except:
        print(traceback.format_exc())
    return str("The deployhement os automatic")

@app.route("/grammar/api/v1/top_lang_errors_for_user/<user_id>")
def top_lang_errors_for_user(user_id):
    print(str(user_id)+' user id')
    try:
        r=models.type_count_for_user(user_id)
        print(str(r))
    except:
        print(traceback.format_exc())
    return jsonify(r)



@app.route("/wordnet_to_rethinkdb/<corpus_to_use>")
def convert(corpus_to_use):
    print("Converting")
    graph=connect_to_neo()
    print(' The graph '+str(graph))
    dict_of_words={}
    name =str(corpus_to_use)
    package = "nltk.corpus"
    try:
        imported = getattr(__import__(package, fromlist=[name]), name)
        list_of_words=[]
        tokenized_corpus=list(imported.words('ca01'))
        print(str(len(tokenized_corpus)))
        bigrams=ngrams(tokenized_corpus,2)
        freq_dist_bigrams=nltk.FreqDist(bigrams)
        #or bigram in freq_dist_bigrams.keys():
        #   collocation={}
        #   collocation['bigram']=bigram
        #   collocation['frequency']=freq_dist_bigrams[bigram]
        #    r.db('lagrammar').table('wordnet').insert(collocation).run()            
        i=0
        tokenized_corpus=['eat']
        for word in tokenized_corpus:
            if word not in list_of_words:
                if graph is not False :
                    word_node=graph.merge_one('word',property_key='name', property_value=word)
                list_of_words.append(word)
                dict_of_words={}
                dict_of_words["word"]=word
                dict_of_words["senses"]=[]
# For neo4j            
                for synset in wn.synsets(word):
                    sense={}
                    antonym={}
                    sense["part_of_speech"]=synset.pos()
                    sense["synonyms"]=[]
                    examples=synset.examples()

# For the lemmas
                    for lemma in synset.lemmas():
                        if lemma.name() == word:#For derivations
                            dforms=lemma.derivationally_related_forms()
                            for dform in dforms:
                                l=dform.name() #for neo4j
                                dform_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"dform",dform_node,definition=dform.synset().definition(),pos=dform.synset().pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:dform {definition:'"+dform.synset().definition().replace("'","\\\'")+"',pos:'"+dform.synset().pos()+"'}]->(m) "
                                graph.cypher.execute(q)
                                
                                                    
                        antonyms_of_lemma=lemma.antonyms()# For antonyms
                        if lemma.name() == word and len(antonyms_of_lemma) > 0:
                            sense['antonyms']=list(ant.name() for ant in antonyms_of_lemma ) 
                            print sense['antonyms']
                            for l in sense['antonyms']: # For neo4j                                
                                antonym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"antonym",antonym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:antonym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)
                                #graph.create(rel)
                   
                                if l not in list_of_words:
                                    tokenized_corpus.append(l)
                        dforms=lemma.derivationally_related_forms()
                        synonym={}
                        lemma_name=lemma.name()
                        synonym['word']=lemma_name                  
                        if len(dforms) >0:
                            synonym['derivationally_related_forms']=list(l.name() for l in dforms)       
                        for example in examples:
                            if lemma_name in nltk.word_tokenize(example):
                                synonym['example']=example
                            examples.remove(example)                            
                        sense["synonyms"].append(synonym)

# For neo4j
                        
                        synonym_node=graph.merge_one('word',property_key='name', property_value=lemma_name)
                        rel=Relationship(word_node,"synonym",synonym_node,definition=synset.definition(),pos=synset.pos())
                        for example in examples:
                            if lemma_name in nltk.word_tokenize(example):
                                print str(lemma_name)+ ' ' +str(example)
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'})-[r:synonym {definition:'"+synset.definition().replace("'","\\\'")+"'}]->(m {name:'"+lemma_name.replace("'","\\\'")+"'}) set r.example='"+example.replace("'","\\\'")+"'"
                                graph.cypher.execute(q)
                        
                        #q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+lemma_name.replace("'","\\\'")+"'}) merge  (n)-[r1:synonym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                        #graph.cypher.execute(q)
                        #graph.create(rel)
                        
                        
                    for l in synset.lemma_names():
                        if l not in list_of_words:
                            tokenized_corpus.append(l)
                    hypernyms=synset.hypernyms()
                    for hypernym in hypernyms:
                        hypernym_names=hypernym.lemma_names()
                        if 'hypernym' not in sense and len(hypernym_names) >0:
                            sense["hypernym"]=[]
                        sense["hypernym"].extend(hypernym_names)


                        for l in hypernym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j
                                hypernym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"hypernym",hypernym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:hypernym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)
                    entailments=synset.entailments()

                    for entailment in entailments:
                        entailment_names=entailment.lemma_names()
                        if 'entailments' not in sense and len(hypernym_names) >0:
                            sense["entailments"]=[]
                        sense["entailments"].extend(entailment_names)    


                        for l in entailment_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                entailment_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"entailment",entailment_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:entailment {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)
                                #graph.create(rel)
                    hyponyms=synset.hyponyms()


                    for hyponym in hyponyms:
                        hyponym_names=hyponym.lemma_names()                    
                        if 'hyponym' not in sense and len(hyponym_names) >0:
                            sense["hyponyms"]=[]                        
                        sense["hyponyms"].extend(hyponym_names)
                        for l in hyponym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                hyponym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"hyponym",hyponym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:hyponym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)

                    pmeronyms=synset.part_meronyms()
                    for pmeronym in pmeronyms:
                        pmeronym_names=pmeronym.lemma_names()                    
                        if 'pmeronym' not in sense and len(pmeronym_names) >0:
                            sense["part_meronyms"]=[]                        
                        sense["part_meronyms"].extend(pmeronym_names)
                        for l in pmeronym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                pmeronym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"pmeronym",pmeronym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:pmeronym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)

                    pholonyms=synset.part_holonyms()
                    for pholonym in pholonyms:
                        pholonym_names=pholonym.lemma_names()                    
                        if 'pholonym' not in sense and len(pholonym_names) >0:
                            sense["part_holonyms"]=[]                        
                        sense["part_holonyms"].extend(pholonym_names)
                        for l in pholonym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                pholonym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"pmeronym",pholonym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:pholonym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)
                                

                    smeronyms=synset.substance_meronyms()
                    for smeronym in smeronyms:
                        smeronym_names=smeronym.lemma_names()                    
                        if 'smeronym' not in sense and len(smeronym_names) >0:
                            sense["substance_meronyms"]=[]                        
                        sense["substance_meronyms"].extend(smeronym_names)
                        for l in smeronym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                smeronym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"smeronym",smeronym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:smeronym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)

                    sholonyms=synset.substance_holonyms()
                    for sholonym in sholonyms:
                        sholonym_names=sholonym.lemma_names()                    
                        if 'sholonym' not in sense and len(sholonym_names) >0:
                            sense["substance_holonyms"]=[]                        
                        sense["substance_holonyms"].extend(sholonym_names)
                        for l in sholonym_names:
                            if l not in list_of_words:
                                tokenized_corpus.append(l)
# For neo4j                                
                                sholonym_node=graph.merge_one('word',property_key='name', property_value=l)
                                rel=Relationship(word_node,"sholonym",sholonym_node,definition=synset.definition(),pos=synset.pos())
                                q=r"match(n {name:'"+word.replace("'","\\\'")+"'}),(m {name:'"+l.replace("'","\\\'")+"'}) merge  (n)-[r1:sholonym {definition:'"+synset.definition().replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(m) "
                                graph.cypher.execute(q)


                    examples=synset.examples() 
                    for example in examples:
                        for syn in sense["synonyms"]:
                            if syn in nltk.word_tokenize(example):
                                if 'examples' not in sense:
                                    sense['examples']=[]
                                sense["examples"].append([example,syn])  
                                break
                    sense["definition"]=synset.definition()
                    
                    dict_of_words["senses"].append(sense)
                #r.db('lagrammar').table('wordnet').insert(dict_of_words).run()
        print("Conversion completed.")
    except:
        traceback.print_exc()
        print('Not able to insert the raw comment details. Is it important? ')


def start_neo(db_dump_location='graph.db'):
    try:
        server = GraphServer(NEO4J_SERVER_DIST_PATH)
    except:
        print(traceback.format_exc())    
        print('Could not find and initialize the neo4j server')
    try:
        # set the name of the graph db dump location
        print db_dump_location
        server.update_server_properties(database_location=db_dump_location)
    except:
        print(traceback.format_exc())    
        print('Some issue in setting the db dump location. Defaulting to '+str(server.conf.get('neo4j-server','org.neo4j.server.database.location')))
    try:
        server.start()
        print str(server.pid) + ' PIDDDDDD   ' 
        print server.conf.get('neo4j-server','org.neo4j.server.database.location')
    except:
        print(traceback.format_exc())    
        print('error in starting')
def stop_neo():
    try:
        server = GraphServer(NEO4J_SERVER_DIST_PATH)
    except:
        print(traceback.format_exc())    
        print('Could not find and initialize the neo4j server')
    try:
        server.stop()
    except:
        print(traceback.format_exc())    
        print('error in stoping')

def connect_to_neo(endpoint=None):
    graph= False
    try:
        if endpoint==None:
            graph= Graph("http://neo4j:441989@localhost:7474/db/data/")
            try:
                graph.schema.create_uniqueness_constraint("word", "name") 
            except:
                print('The uniqueness constraint already exists.')
            return graph
        else :
            graph= Graph("http://neo4j:441989@localhost:7474"+str(endpoint))
            try:
                graph.schema.create_uniqueness_constraint("word", "name") 
            except:
                print('The uniqueness constraint already exists.')
            return graph
        
    except :
        print(traceback.format_exc())    
        return False

def connect_to_rethinkdb():
    try:
        conn=r.connect(host = 'localhost',port = 28015)
        try:
	    r.db_create('lagrammar').run(conn)
	except :
	    print('The db exists')
        try:
	    r.db('lagrammar').table_create('wordnet').run(conn)    
        except:
	    print('The table exists')
        return conn
    except:
        print(traceback.format_exc())
	return False




@app.route("/add_examples/<corpus_to_use>")
def add_examples(corpus_to_use):
    print("Converting")
    stop_neo()
    start_neo('/home/snehal/data/graphwithexamples.db')
    graph=connect_to_neo()
    print(' The graph '+str(graph))
    dict_of_words={}
    name =str(corpus_to_use)
    package = "nltk.corpus"
    try:
        imported = getattr(__import__(package, fromlist=[name]), name)
        sentences=imported.sents()
        for sentence in sentences:
            words = sentence
            text=' '.join(sentence) 
            contexts=disambiguate(text)
            tagged_sent = pos_tag(words)
            propernouns = [word for word,pos in tagged_sent if pos == 'NNP']
            for context in contexts:
                ambiguous=context[0]
                synset=context[1]
                if synset is  None:
                    continue
                if ambiguous not in propernouns:
                    ambiguous=str.lower(str(ambiguous))
                print ambiguous
                context=synset.definition()
                pos=synset.pos()
                q=r"merge (n:word {name:'"+ambiguous.replace("'","\\\'")+"'})"
                graph.cypher.execute(q)
#                print text + ' ::::::::: '+ambiguous
                q=r"merge (n:word {name:'"+ambiguous.replace("'","\\\'")+"'}) merge (n)-[r:synonym {definition:'"+context.replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(n) with r."+name+"_examples as re,r where re is null set r."+name+"_examples=['"+text.replace("'","\\\'")+"'] return r"
                result=graph.cypher.execute(q)
                if ambiguous =='the':
                    print q + ' \n '+' ##################################################################################'
                    print len(result)
                if result is None or len(result)==0:
                    q=r"merge (n:word {name:'"+ambiguous.replace("'","\\\'")+"'}) merge (n)-[r:synonym {definition:'"+context.replace("'","\\\'")+"',pos:'"+synset.pos()+"'}]->(n) with r."+name+"_examples as re,r where re is not null set r."+name+"_examples=['"+text.replace("'","\\\'")+"']+re return r"
                    if ambiguous =='the':
                        print q + ' \n '+' ##################################################################################'
                    graph.cypher.execute(q)


    except:
        print ('Some error in the add_examples API method')   
        print(traceback.format_exc())                                     
        
        

@app.route("/add_example_sentences/<corpus_to_use>")
def add_example_sentences(corpus_to_use):
    print("Converting")
#    stop_neo()
#    start_neo('/home/snehal/data/examplesentencesgraph.db')
    try:
        graph=connect_to_neo()
        print(' The graph '+str(graph))
        dict_of_words={}
        name =str(corpus_to_use)
        package = "nltk.corpus"
        imported = getattr(__import__(package, fromlist=[name]), name)
        tokenized_corpus=list(imported.words())
        sentences=imported.sents()
        index=0
        bigrams=ngrams(tokenized_corpus,2)
        freq_dist_bigrams=nltk.FreqDist(bigrams)
        print 'about to iterate'        
        for sentence in sentences:
        
#            if index <57340:
#                index=index+1
#                continue
            words = sentence
            text=' '.join(sentence) 
            tagged_sent = pos_tag(words)
            propernouns = [word for word,pos in tagged_sent if pos == 'NNP']            
            if index%1000 ==0:
                print text
            prev=None
            orderi=0
            for word in words:
                if word not in propernouns:
                    word=str.lower(str(word))            
                q=r"merge (n:word {name:'"+word.replace("'","\\\'")+"'})"
                graph.cypher.execute(q)
                if prev is not None:
                    q=r"match (n:word {name:'"+prev.replace("'","\\\'")+"'}),(m:word {name:'"+word.replace("'","\\\'")+"'})  merge (n)-[r:sentence {index:'"+str(index+57340)+"', prob:'"+str(freq_dist_bigrams[(prev,word)])+"',orderi:"+str(orderi)+"}]->(m) return r"
                    result=graph.cypher.execute(q)
                    orderi=orderi+1
                prev=word
            index=index+1
        return jsonify({'Completion':'Success'})     
    except:
        print ('Some error in the add_examples API method')   
        print(traceback.format_exc())                         
        return jsonify({'Completion':'Failure'})                 
                
                
                


@app.route("/add_syntdep_to_new_graph/<corpus_to_use>")
def add_syntactic_dependencies_to_new_graph(corpus_to_use):
    print("Converting")
    start_neo('/home/snehal/data/dependencygraph.db')
    graph=connect_to_neo()
    print(' The graph '+str(graph))
    dict_of_words={}
    name =str(corpus_to_use)
    package = "nltk.corpus"
    try:
        imported = getattr(__import__(package, fromlist=[name]), name)
        tokenized_corpus=list(imported.words())
        sentences=imported.sents()
        index=0
        parser=Parser()        
        for sentence in sentences:
            if index <3975:
                index=index+1
                continue
            words = sentence
            text=' '.join(sentence) 
            dependencies=None
            try:
                dependencies = parser.parseToStanfordDependencies(text)
            except:
                print('Error in dependency parsing. Skipping the sentence.....')
            if dependencies ==None  :
                continue
            dependency_tuples = [(rel, gov.text, dep.text) for rel, gov, dep in dependencies.dependencies]
            tagged_sent = pos_tag(words)
            propernouns = [word for word,pos in tagged_sent if pos == 'NNP']            
            if index%1000 ==0:
                print text
            for dependency_tuple in dependency_tuples:
                s_word=dependency_tuple[1]
                e_word=dependency_tuple[2]
                if s_word not in propernouns:
                    s_word=str.lower(str(s_word))
                if e_word not in propernouns:
                    e_word=str.lower(str(e_word))
                dependency_type=dependency_tuple[0]
#                print s_word+ e_word+dependency_type
                q=r"merge (n:word {name:'"+s_word.replace("'","\\\'")+"'}) return n"
                graph.cypher.execute(q)
                q=r"merge (m:word {name:'"+e_word.replace("'","\\\'")+"'}) return m"
                graph.cypher.execute(q)
                q=r"match (n:word {name:'"+s_word.replace("'","\\\'")+"'})-[r:dependency {type:'"+str(dependency_type).replace("'","\\\'")+"'}]->(m:word {name:'"+e_word.replace("'","\\\'")+"'})   return r"
                result=graph.cypher.execute(q)
#                print result 
                if result is not None and len(result)>0:
                    print str(index)+' >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'
                    q=r"match (n:word {name:'"+s_word.replace("'","\\\'")+"'}),(m:word {name:'"+e_word.replace("'","\\\'")+"'})  merge (n)-[r:dependency {type:'"+str(dependency_type).replace("'","\\\'")+"'}]->(m) with r.index as ri,r set r.index=['"+str(index)+"']+ri return r"
                    graph.cypher.execute(q)
                else:
                    q=r"match (n:word {name:'"+s_word.replace("'","\\\'")+"'}),(m:word {name:'"+e_word.replace("'","\\\'")+"'})  merge (n)-[r:dependency {type:'"+str(dependency_type).replace("'","\\\'")+"'}]->(m) set r.index=['"+str(index)+"'] return r"
                    graph.cypher.execute(q)
            index=index+1                                


    except:
        print ('Some error in the add_examples API method')   
        print(traceback.format_exc())                                     
                
                


@app.route("/create_sense_graph/<corpus_to_use>")
def create_sense_graph(corpus_to_use):
    print("Converting")
    graph=connect_to_neo()
    print(' The graph '+str(graph))
    dict_of_words={}
    name =str(corpus_to_use)
    package = "nltk.corpus"
    try:
        imported = getattr(__import__(package, fromlist=[name]), name)
        list_of_words=[]
        tokenized_corpus=list(imported.words())
        print(str(len(tokenized_corpus)))
        bigrams=ngrams(tokenized_corpus,2)
        freq_dist_bigrams=nltk.FreqDist(bigrams)
        i=0
        tokenized_corpus=['name_and_address']
        set_tokenized_corpus=set()
        set_tokenized_corpus_add=set_tokenized_corpus.add
        for word in tokenized_corpus:
            #tokenized_corpus=[ x for x in tokenized_corpus if not (x in seen or set_tokenized_corpus_add(x))]
            with open('/home/snehal/wordlist','a') as wordlist:
                wordlist.write(word+"\n")
            if True:
                #list_of_words.add(word)
                dict_of_words={}
                dict_of_words["word"]=word
                dict_of_words["senses"]=[]
# For neo4j
                for synset in wn.synsets(word):
                    definition=synset.definition()
                    q=r"merge(n:sense {definition:'"+definition.replace("'","\\\'")+"'}) return n"
                    graph.cypher.execute(q)
                    
                    for lemma in synset.lemmas():
                        if lemma.name() not in tokenized_corpus:
                            tokenized_corpus.append(lemma.name())
                        q=r"merge(n:word {name:'"+lemma.name().replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+definition.replace("'","\\\'")+"'}) merge (n)-[r:synonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        if lemma.name() == word:
                            dforms=lemma.derivationally_related_forms()
                            for dform in dforms:
                                dform_word=dform.name()
                                if dform_word not in tokenized_corpus:
                                    tokenized_corpus.append(dform_word)
                                dform_definition=dform.synset().definition()
                                q=r"merge(n:sense {definition:'"+dform_definition.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+dform_word.replace("'","\\\'")+"'}) merge (m)-[r:synonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                q=r"match(n:word {name:'"+dform_word.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+lemma.name().replace("'","\\\'")+"'}) merge (m)-[r:derivation {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                                    
                        antonyms_of_lemma=lemma.antonyms()
                        if lemma.name() == word and len(antonyms_of_lemma) > 0:
                            for ant in antonyms_of_lemma:
                                ant_word=ant.name()
                                ant_definition=ant.synset().definition()
                                q=r"merge(n:sense {definition:'"+ant_definition.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+ant_word.replace("'","\\\'")+"'}) merge (m)-[r:synonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                q=r"match(n:word {name:'"+ant_word.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+word.replace("'","\\\'")+"'}) merge (m)-[r:antonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                if ant_word not in tokenized_corpus:
                                    tokenized_corpus.append(ant_word)
                                
                    hypernyms=synset.hypernyms()
                    for hypernym in hypernyms:
                        hypernym_definition=hypernym.definition()
                        q=r"merge(n:sense {definition:'"+hypernym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:hypernym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        hypernym_names=hypernym.lemma_names()
                        for l in hypernym_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)

                    entailments=synset.entailments()
                    for entailment in entailments:
                        entailment_definition=entailment.definition()
                        q=r"merge(n:sense {definition:'"+entailment_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:entailment {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        entailment_names=entailment.lemma_names()
                        for l in entailment_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)

                    part_holonyms=synset.part_holonyms()
                    for part_holonym in part_holonyms:
                        part_holonym_definition=part_holonym.definition()
                        q=r"merge(n:sense {definition:'"+part_holonym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:part_holonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        part_holonym_names=part_holonym.lemma_names()
                        for l in part_holonym_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)

                    part_meronyms=synset.part_meronyms()
                    for part_meronym in part_meronyms:
                        part_meronym_definition=part_meronym.definition()
                        q=r"merge(n:sense {definition:'"+part_meronym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:part_meronym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        part_meronym_names=part_meronym.lemma_names()
                        for l in part_meronym_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)


                    substance_holonyms=synset.substance_holonyms()
                    for substance_holonym in substance_holonyms:
                        substance_holonym_definition=substance_holonym.definition()
                        q=r"merge(n:sense {definition:'"+substance_holonym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:substance_holonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        substance_holonym_names=substance_holonym.lemma_names()
                        for l in substance_holonym_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)


                    substance_meronyms=synset.substance_meronyms()
                    for substance_meronym in substance_meronyms:
                        substance_meronym_definition=substance_meronym.definition()
                        q=r"merge(n:sense {definition:'"+substance_meronym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:substance_meronym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        substance_meronym_names=substance_meronym.lemma_names()
                        for l in substance_meronym_names:
                            if l not in tokenized_corpus:
                                tokenized_corpus.append(l)


        print("Conversion completed.")
    except:
        traceback.print_exc()
        print('Not able to insert the raw comment details. Is it important? ')
                


@app.route("/add_all_senses/<corpus_to_use>")
def add_all_senses(corpus_to_use):
    print("Converting")
    graph=connect_to_neo()
    print(' The graph '+str(graph))
    dict_of_words={}
    name =str(corpus_to_use)
    package = "nltk.corpus"
    try:
        i=0
        all_senses=wn.all_synsets()       
        for synset in all_senses:
            definition=synset.definition()
            q=r"merge(n:sense {definition:'"+definition.replace("'","\\\'")+"'}) return n"
            graph.cypher.execute(q)
            if True:
                if True:
                    for lemma in synset.lemmas():
                        q=r"merge(n:word {name:'"+lemma.name().replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+definition.replace("'","\\\'")+"'}) merge (n)-[r:synonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        if True:
                            dforms=lemma.derivationally_related_forms()
                            for dform in dforms:
                                dform_word=dform.name()
                                dform_definition=dform.synset().definition()
                                q=r"merge(n:sense {definition:'"+dform_definition.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+dform_word.replace("'","\\\'")+"'}) merge (m)-[r:synonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                q=r"match(n:word {name:'"+dform_word.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+lemma.name().replace("'","\\\'")+"'}) merge (m)-[r:derivation {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                                    
                        antonyms_of_lemma=lemma.antonyms()
                        if len(antonyms_of_lemma) > 0:
                            for ant in antonyms_of_lemma:
                                ant_word=ant.name()
                                ant_definition=ant.synset().definition()
                                q=r"merge(n:sense {definition:'"+ant_definition.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+ant_word.replace("'","\\\'")+"'}) merge (m)-[r:synonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                q=r"match(n:word {name:'"+ant_word.replace("'","\\\'")+"'}) with n merge(m:word {name:'"+lemma.name().replace("'","\\\'")+"'}) merge (m)-[r:antonym {strength:"+str(0)+"}]->(n) return r"
                                graph.cypher.execute(q)
                                
                    hypernyms=synset.hypernyms()
                    for hypernym in hypernyms:
                        hypernym_definition=hypernym.definition()
                        q=r"merge(n:sense {definition:'"+hypernym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:hypernym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        hypernym_names=hypernym.lemma_names()

                    hyponym=synset.hyponyms()
                    for hyponym in hyponyms:
                        hyponym_definition=hyponym.definition()
                        q=r"merge(n:sense {definition:'"+hyponym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (m)-[r:hyponym {strength:"+str(0)+"}]->(n) return r"
                        graph.cypher.execute(q)
                        hypernym_names=hypernym.lemma_names()

                    entailments=synset.entailments()
                    for entailment in entailments:
                        entailment_definition=entailment.definition()
                        q=r"merge(n:sense {definition:'"+entailment_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:entailment {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        entailment_names=entailment.lemma_names()

                    part_holonyms=synset.part_holonyms()
                    for part_holonym in part_holonyms:
                        part_holonym_definition=part_holonym.definition()
                        q=r"merge(n:sense {definition:'"+part_holonym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:part_holonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        part_holonym_names=part_holonym.lemma_names()

                    part_meronyms=synset.part_meronyms()
                    for part_meronym in part_meronyms:
                        part_meronym_definition=part_meronym.definition()
                        q=r"merge(n:sense {definition:'"+part_meronym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:part_meronym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        part_meronym_names=part_meronym.lemma_names()

                    substance_holonyms=synset.substance_holonyms()
                    for substance_holonym in substance_holonyms:
                        substance_holonym_definition=substance_holonym.definition()
                        q=r"merge(n:sense {definition:'"+substance_holonym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:substance_holonym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        substance_holonym_names=substance_holonym.lemma_names()


                    substance_meronyms=synset.substance_meronyms()
                    for substance_meronym in substance_meronyms:
                        substance_meronym_definition=substance_meronym.definition()
                        q=r"merge(n:sense {definition:'"+substance_meronym_definition.replace("'","\\\'")+"'}) with n merge(m:sense {definition:'"+synset.definition().replace("'","\\\'")+"'}) with n,m merge (n)-[r:substance_meronym {strength:"+str(0)+"}]->(m) return r"
                        graph.cypher.execute(q)
                        substance_meronym_names=substance_meronym.lemma_names()

            
        print("Conversion completed.")
    except:
        traceback.print_exc()
        print('Not able to insert the raw comment details. Is it important? ')
                
                
            
if __name__ == '__main__':
    app.run(host='localhost',port=5001)

