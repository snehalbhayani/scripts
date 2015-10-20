import sys
import json
import io
import sys
import rethinkdb as r
from rethinkdb import RqlRuntimeError
import traceback

def extract(app):
# Connect to the local rethinkdb instance
    r.connect('localhost', 28015).repl()
    comment_details=r.db('lagrammar').table('analyzed_comments').run()
    return comment_details

def type_count_for_user(user_id):
    user_id=int(user_id)
    r.connect('localhost', 28015).repl()    
    type_count_hash = r.db('lagrammar').table('analyzed_comments').group(index='type').filter({'user_id': user_id}).count().run()
    return type_count_hash
