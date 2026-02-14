from flask import Flask, request

app = Flask(__name__)

@app.route("/sms", methods=["POST"])
def sms():
    message = request.form.get("Body", "")
    sender = request.form.get("From", "")
    print(f"Message from {sender}: {message}")
    return "", 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
