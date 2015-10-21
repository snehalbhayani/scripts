import psycopg2
import sys
import psycopg2.extras
from elasticsearch import Elasticsearch
 
def create_item_index():
	#Define our connection string

    conn_string = "host='localhost' dbname='test2' user='postgres' password='441989'"
 
	# print the connection string we will use to connect
    print "Connecting to database\n	->%s" % (conn_string)
 
	# get a connection, if a connect cannot be made an exception will be raised here
    conn = psycopg2.connect(conn_string)
 
	# conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor()
    cursor.execute("select  items.id, items.properties, items.lesson_id, items.item_type_id, items.parent_id, itags.tag_id, tags.slug from items as items left outer join item_tags as itags on items.id=itags.item_id left outer join tags  on tags.id=itags.tag_id order by items.id")
    records = cursor.fetchall()
	# Then we connect to an elasticsearch server
    es = Elasticsearch()
    es.indices.create(index='learnapt', ignore=400, body={"mappings" : {"type1" : {"_source" : { "enabled" : 'true' }, \
            "properties" : { \
                "item_id" : { "type" : "integer", "index" : "analyzed" }, \
                "lesson_id" : { "type" : "integer", "index" : "analyzed" }, \
                "item_type_id" : { "type" : "integer", "index" : "analyzed" }, \
                "item_title" : { "type" : "string", "index" : "analyzed" }, \
                "item_link_url" : { "type" : "string", "index" : "analyzed" }, \
                "item_tags" : { "type" : "integer", "index" : "analyzed" } \
                }}}})
    old_item_id=-1
    for record in records:
        parent_id=record[4]
        item_id=record[0]
        lesson_id=record[2]
        item_type_id=record[3]
        tag=record[6]
        if record[1] is None:
            continue
        item_contents=record[1].split('", "')
        if item_id is old_item_id and tag is not None:
            document['item_tags'].append(tag.replace('-','_'))
        else:
            document={'item_id':item_id,'lesson_id':lesson_id,'item_type_id':item_type_id}
            if tag is not None:
                document['item_tags']=[tag.replace('-','_')]
        for item_content in item_contents:
            key_value=item_content.strip().split('=>')
            if len(key_value)<2 or len(key_value)%2 is not 0:
                continue
            document['item_'+key_value[0].strip().replace('"','')]=key_value[1].strip().replace('"','')
        if item_id != old_item_id and old_item_id != -1:
#            print 'item_id being inserted '+str(old_item_id)
            es.create('learnapt', 'item',old_document,int(old_item_id))
            try:
                print old_document['item_tags']
            except:
                pass
        old_item_id=item_id
        old_document=document
    print "Converted!\n "

def create_lesson_index():
	#Define our connection string

    conn_string = "host='localhost' dbname='test2' user='postgres' password='441989'"
 
	# print the connection string we will use to connect
    print "Connecting to database\n	->%s" % (conn_string)
 
	# get a connection, if a connect cannot be made an exception will be raised here
    conn = psycopg2.connect(conn_string)
 
	# conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor()
    cursor.execute("select  lessons.id, lessons.name, lessons.slug, lessons.cover_image, lessons.sub_title, itags.tag_id, tags.slug as tag_name, users.first_name, users.last_name, users.username from lessons as lessons  left outer join lesson_tags as itags on lessons.id=itags.lesson_id left outer join tags  on tags.id=itags.tag_id left outer join users on users.id=lessons.owner_id order by lessons.id;")
    records = cursor.fetchall()
	# Then we connect to an elasticsearch server
    es = Elasticsearch()
    es.indices.create(index='learnapt', ignore=400, body={"mappings" : {"type1" : {"_source" : { "enabled" : 'true' }, \
            "properties" : { \
                "lesson_id" : { "type" : "integer", "index" : "analyzed" }, \
                "lesson_name" : { "type" : "string", "index" : "analyzed" }, \
                "lesson_slug" : { "type" : "string", "index" : "analyzed" }, \
                "lesson_cover_image" : { "type" : "string", "index" : "analyzed" }, \
                "lesson_owner_name" : { "type" : "string", "index" : "analyzed" }, \
                "lesson_tags" : { "type" : "string", "index" : "analyzed" }, \
                "lesson_collaborators" : { "type" : "string", "index" : "analyzed" }}}}})
    old_lesson_id=-1
    for record in records:
        lesson_id=record[0]
        lesson_name=record[1]
        lesson_slug=record[2]
        lesson_sub_title=record[4]
        lesson_cover_image=record[3]
        lesson_owner_name=str(record[7])+ ' '+ str(record[8])
        tag=record[6]
        if record[1] is None:
            continue
        if lesson_id is old_lesson_id and tag is not None:
            if 'lesson_tags' not in document:
                document['lesson_tags']=[]
            document['lesson_tags'].append(tag.replace('-','_'))
        else:
            document={'lesson_id':lesson_id,'lesson_name':lesson_name, 'lesson_slug':lesson_slug, 'lesson_sub_title':lesson_sub_title, 'lesson_cover_image':lesson_cover_image, 'lesson_owner_name':lesson_owner_name}
            if tag is not None:
                document['lesson_tags']=[tag.replace('-','_')]
        if lesson_id != old_lesson_id and old_lesson_id != -1:
            #print 'lesson_id being inserted '+str(old_lesson_id)
            cursor.execute("select collaborator_id, users.first_name, users.last_name from lesson_collaborators as ipc left outer join users on ipc.collaborator_id = users.id where lesson_id="+str(old_lesson_id)+" and title='Writer'")
            collabs=cursor.fetchall();

            if len(collabs)>0:
                old_document['lesson_collaborators']=list([ str(collab[1])+ ' '+str(collab[2]) for collab in collabs ])

            es.create('learnapt', 'lesson',old_document,int(old_lesson_id))
            try:
                print old_document['lesson_collaborators']
            except:
                pass
        old_lesson_id=lesson_id
        old_document=document

    print "Converted!\n "

def create_user_index():
	#Define our connection string

    conn_string = "host='localhost' dbname='test2' user='postgres' password='441989'"
 
	# print the connection string we will use to connect
    print "Connecting to database\n	->%s" % (conn_string)
 
	# get a connection, if a connect cannot be made an exception will be raised here
    conn = psycopg2.connect(conn_string)
 
	# conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor()
    cursor.execute("select users.id, users.first_name, users.last_name, users.username, users.email  from users order by users.id;")
    records = cursor.fetchall()
	# Then we connect to an elasticsearch server
    es = Elasticsearch()
    es.indices.create(index='learnapt', ignore=400, body={"mappings" : {"type1" : {"_source" : { "enabled" : 'true' }, \
            "properties" : { \
                "user_id" : { "type" : "integer", "index" : "analyzed" }, \
                "user_name" : { "type" : "string", "index" : "analyzed" }, \
                "user_fullname" : { "type" : "string", "index" : "analyzed" }, \
                "user_email" : { "type" : "string", "index" : "analyzed" }}}}})
    old_lesson_id=-1
    for record in records:
        userid=record[0]
        username=record[3]
        full_name=str(record[1]) + ' '+str(record[2])
        email=str(record[4])
        document={'user_id':userid,'user_name':username,'user_fullname':full_name,'user_email':email}
        es.create('learnapt', 'user',document,userid)
        print document
    print "Converted!\n "

if __name__ == "__main__":
    create_item_index()
    create_lesson_index()
    create_user_index()

