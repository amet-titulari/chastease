from flask import  request, jsonify, current_app, session

from. import journal


from flask import render_template

@journal.route('/')
def index():

    content = f'    <div class="container">\
                        <h1>Das ist das Journal!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    return render_template('index.html', content=content) 

