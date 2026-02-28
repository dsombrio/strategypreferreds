from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head><title>DRIP Calc</title></head>
<body style="background:#0d1117;color:#f0f6fc;font-family:sans-serif;text-align:center;padding:50px;">
    <h1>DRIP Calculator</h1>
    <p>Testing basic Flask deployment...</p>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
