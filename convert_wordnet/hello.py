from flask import Flask
app = Flask(__name__)


print(__name__+' >>>>>>>')
@app.route("/sayhello")
def hello():
    return "<h1 style='color:blue'>Hiiiiiiiiiiiiiiiii! Flask behind uncorn and nginx</h1>"

if __name__ == "__main__":
    print('Running the app with name as __main__')
    app.run(host='0.0.0.0')
