import requests
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

def post_request(json_request):
    data = {}
    # r = requests.post('url, data=data)

@app.route("/", methods=["POST", "GET"])
def process_update():
    if request.method == "POST":
        print('update', request)
        json_request = request.get_json()

        with open("last_req.json", 'w') as js:
            js.write(json.dumps(json_request))

        print(json_request)
        return "ok got your post!", 200
        
    if request.method == "GET":
        with open("last_req.json") as js:
            a = json.load(js)
        return jsonify(a)

if __name__ == '__main__':
   app.run(debug = True)
