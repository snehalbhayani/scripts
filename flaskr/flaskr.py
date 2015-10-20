# all the imports
import logging
from py2neo import Node, Relationship, Graph, neo4j
import sys
import rethinkdb as r
from rethinkdb import RqlRuntimeError
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash,jsonify
import traceback
import staticpaths
# configuration
DATABASE = 'lagrammar'
HOSTNAME='localhost'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)

@app.route('/v1/wordnet/<arg1>/<arg2>/find_examples/',methods=['GET','POST'])
def find_examples(arg1=None,arg2=None):
    word=arg1
    try:
        if word ==None:
            return jsonify('Some problem with the parameters pass with GET request')
        else:
            graph=connect_to_neo()
        examples={}
        q=r"match (n {name:'"+word.replace("'","\\\'")+"'})-[r:synonym]->(m) return r,m "
        results=graph.cypher.execute(q)
        
        for result in results:
            
            synonym=result[0]
            definition=result[0].properties['definition']
            if synonym.properties['example'] and synonym.properties['example'] != 'None' :
                end_word=result[1].properties['name']    
                if definition not in examples:
                    examples[definition]={}                
                if end_word not in examples[definition]:
                    examples[definition][end_word]=[]
                examples[definition][end_word].append(synonym.properties['example'])
        a=jsonify(examples)
    except:
        app.logger.info(traceback.format_exc())                        
        app.logger.info('Http method not supported in this version.')
    return a
    

@app.route('/v1/wordnet/<arg1>/<arg2>/group_by_relation/',methods=['GET','POST'])
def group_by_relation(arg1=None,arg2=None):
    word=arg1
    rels=arg2
    try:
        rels_list=rels.split('_')
        if len(rels_list) ==0:
            app.logger.info ('No relations specified')
        elif rels != 'all':
            construction=""
            for rel in rels_list:
                construction=construction+":"+rel+'|'
            dict_of_details=(find_and_group_by_relation(word,construction[:-1]))
        else :
            dict_of_details=(find_and_group_by_relation(word,''))
        app.logger.info (dict_of_details)
    except:
        app.logger.info(traceback.format_exc())                    
        app.logger.info('Some error ')
    return jsonify(dict_of_details)

def find_and_group_by_relation(word,relation):
    graph=connect_to_neo()
    q=r"match(n {name:'"+word.replace("'","\\\'")+"'})-[r"+relation+"]->(m) return type(r),r,m"
    app.logger.info (q)
    edges=graph.cypher.execute(q)
    edge_senses={}
    edge_senses['word']=word
    edge_senses['pronunciation_url']=get_pronunciation_url(word)        
        
    i=-1
    while i < len(edges)-1:
        i=i+1        
        edge=edges[i]
        relationship_type=edge[0]
        relationship=edge[1]
        node=edge[2]
        if node.properties['name'] == word:
            continue
        definition=relationship.properties['definition']
        if relationship_type not in edge_senses.keys():
            edge_senses[relationship_type]={}
        if definition not in edge_senses[relationship_type].keys():
            edge_senses[relationship_type][definition]=[]
        edge_senses[relationship_type][definition].append(node.properties['name'])
    return edge_senses

@app.route('/v1/wordnet/<arg1>/<arg2>/group_by_definition/',methods=['GET','POST'])
def group_by_definition(arg1=None,arg2=None):
    word=arg1
    rels=arg2
    try:
        rels_list=rels.split('_')
        if len(rels_list) ==0:
            app.logger.info ('No relations specified')
        elif rels != 'all':
            construction=""
            for rel in rels_list:
                construction=construction+":"+rel+'|'
            dict_of_details=(find_and_group_by_definition(word,construction[:-1]))
        else:
            dict_of_details=(find_and_group_by_definition(word,''))
        return jsonify(dict_of_details)
    except:
        return ('There was some error. Request you to contact the programmer.')

def find_and_group_by_definition(word,relation):
    graph=connect_to_neo()
    q=r"match(n {name:'"+word.replace("'","\\\'")+"'})-[r"+relation+"]->(m) return type(r),r,m"
    edges=graph.cypher.execute(q)
    app.logger.info (q)
    edge_senses={}
    edge_senses['word']=word
    edge_senses['pronunciation_url']=get_pronunciation_url(word)        
    
    i=-1
    while i < len(edges)-1:
        i=i+1
        edge=edges[i]
        relationship_type=edge[0]
        relationship=edge[1]
        node=edge[2]
        if node.properties['name'] == word:
            continue
        definition=relationship.properties['definition']
        if definition not in edge_senses.keys():
            edge_senses[definition]={}
        if relationship_type not in edge_senses[definition].keys():
            edge_senses[definition][relationship_type]=[]
        edge_senses[definition][relationship_type].append(node.properties['name'])
    return edge_senses


@app.route('/v1/wordnet/<arg1>/<arg2>/<arg3>/find_similarity/',methods=['GET','POST'])
def find_similarity(arg1=None,arg2=None,arg3=None):
    start_word=arg1
    end_word=arg2
    rels_to_use=None
    if arg3 is not None and str(arg3) != "" :
        rels_to_use=arg3
    if start_word ==None or end_word==None:
        app.logger.error("Please specify both the words.")
        return False
    paths=[]
    try:
        graph=connect_to_neo()
        if rels_to_use is not None and rels_to_use !='all' :
            q=r"match (n {name:'"+start_word+"'}), (m {name:'"+end_word+"'}), p=allShortestPaths((n)-[:"+rels_to_use.replace('_','|:')+"*]-(m)) return relationships(p)"
        elif rels_to_use =='all':
            q=r"match (n {name:'"+start_word+"'}), (m {name:'"+end_word+"'}), p=allShortestPaths((n)-[*]-(m)) return relationships(p)"    
        results=graph.cypher.execute(q)
        for result in results:
            path={}
            relations=result[0]
            if len(relations) >0:
                path['start_word']=start_word
                path['end_word']=end_word                
            for relation in relations:
                if 'subpaths' not in path:
                    path['subpaths']=[]    
                r={}
                r['from']=relation.start_node.properties['name']
                r['to']=relation.end_node.properties['name']
                r['definition']=relation.properties['definition']
                r['part_of_speech']=relation.properties['pos']
                r['relation']=relation.type
                examples=relation.properties['example']
                if examples:
                    r['examples']=examples
                
                path['subpaths'].append(r)
            paths.append(path)
        return jsonify({'paths':paths})
    except:
        app.logger.error(traceback.format_exc())            
        return ('There was some error. Request you to contact the programmer.')
    



def connect_to_neo():
    try:
        graph= Graph("http://neo4j:441989@45.55.220.39:7474/db/data/")
        app.logger.debug('Connected to the graph database.')
        return graph
    except:
        app.logger.error(traceback.format_exc())    
        return False


def get_pronunciation_url(word):
    return str(staticpaths.URL_FOR_PRONUNICATION_FILES)+word+'.mp3'

# In case we want to run the app on a standalone basis
if __name__ == '__main__':

    logger = logging.getLogger('wordnet')
    hdlr = logging.FileHandler('/var/tmp/wordnet.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(logging.INFO)
    logger.info('The logger was set.')
    app.logger.addHandler(hdlr) 
    app.logger.setLevel(logging.INFO)
    app.logger.info('The logger was set.')
    app.run(host='45.55.220.39', port=5006)

