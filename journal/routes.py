from flask import render_template, redirect, url_for, flash

from . import journal

from .models import db, Journal
from .forms import JournalForm



from flask import render_template

@journal.route('/')
def index():

    content = f'    <div class="container">\
                        <h1>Das ist das Journal!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    return render_template('index.html', content=content) 

@journal.route('/new', methods=['GET', 'POST'])
def new_journal():
    form = JournalForm()
    if form.validate_on_submit():
        journal_entry = Journal(
            shave=form.shave.data,
            edge=form.edge.data,
            ruined=form.ruined.data,
            orgasm=form.orgasm.data,
            journal=form.journal.data,
            benutzer_id=form.benutzer_id.data  # Stellen Sie sicher, dass diese ID korrekt festgelegt ist
        )
        db.session.add(journal_entry)
        db.session.commit()
        flash('Journal-Eintrag wurde erfolgreich hinzugefügt.')
        return redirect(url_for('some_function'))  # Leiten Sie zu einer relevanten Seite weiter

    return render_template('journal/new_journal.html', title='Neues Journal', form=form)

