from flask import Flask, redirect, request

app = Flask(__name__)

@app.before_request
def redirect_to_https():
    # Redirect all HTTP requests to HTTPS
    return redirect(f"https://{request.host}{request.path}", code=301)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
