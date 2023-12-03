import random
from flask import Flask
from flask_mail  import Mail, Message
from flask import flash, redirect, render_template, request, session, url_for, abort
import pymssql
from smtplib import SMTPException
from flask_wtf import FlaskForm
from wtforms import EmailField, SubmitField
from wtforms.validators import InputRequired, Email
from config import ProductionConfig as pc, DevelopementConfig as dc


# создание экземпляра приложения
app = Flask(__name__)

# подключение настроек приложения из файла
app.config.from_object('config.ProductionConfig')

# инициализирует расширения
mail = Mail(app)

def callproc(proc: str, params: tuple) -> dict:
  with pymssql.connect(pc.SQL_SERVER, 
                       pc.SQL_USER, 
                       pc.SQL_PSWD, 
                       pc.SQL_DB) as conn:
      with conn.cursor(as_dict=True) as cursor: 
          cursor.callproc(proc, params)          
          res_dict = [*cursor]
          conn.commit()
          return res_dict
      
class LoginForm(FlaskForm):    
    email = EmailField('Адрес вашей корпоративной эл.почты (@tele2.ru): ', validators=[Email(), InputRequired()]) 
    submit = SubmitField("Получить код")

def send_email(subject: str, body: str, users: list[str]) -> tuple[bool, str | None]:
    """
        Отправляет письмо на адреса электронной почты пользователей

        :param: subject: заголовок письма, body: текст письма, users: список адресов эл. почты
        :return: кортеж с информацией о статусе отправки письма (true/false и описание ошибки(при наличии))
        """
    try:
        with mail.connect() as conn:
            for user in users:
                msg = Message(recipients=[user],
                              body=body,
                              subject=subject)

                conn.send(msg)
            #app.logger.info(f'Письмо с темой "{subject}" отправлено пользователю {user}')
            return (True, )
    except SMTPException as err:
        return (False, str(err))  
    
 


@app.route("/", methods=["POST", "GET"])
def index():
    if 'logged_in' in session:
        if request.method == "POST":
            pass
        else:
            return render_template('index.html', title='Каталог "Книжного перекрестка"',
                                   avl_books=callproc('[dbo].[sp_get_available_books]', (session['userLogged'],)),                                   
                                   taken_books=callproc('[dbo].[sp_get_taken_books]', (session['userLogged'],)),
                                   menu=callproc('[dbo].[sp_get_menu]', ()), user=session['userLogged'].split('@')[0])
    else:
        return redirect(url_for('login'))
    
@app.route("/about")
def about():
    if 'logged_in' in session:
        
        return render_template('about.html', title='О проекте "Книжный перекресток"', menu=callproc('[dbo].[sp_get_menu]', ()),
                               user=session['userLogged'].split('@')[0])
    else:
        return redirect(url_for('login'))


@app.route("/add_book", methods=["POST", "GET"])
def add_book():
    
    if 'logged_in' in session:        
        if request.method == "POST":
            # title, author, year, status, add_userid
            res = callproc('[dbo].[sp_add_new_book]', (session['userLogged'], 
                                            request.form["title-book"].strip(),
                                            request.form["author-book"].strip(),
                                            request.form["genre_id"].strip(),
                                            request.form["year-book"].strip(),
                                            request.form["pages"].strip()
                                            ))            
            if not res[0]['result']:
                flash(f"Ошибка добавления книги в каталог. Если не удается устранить ошибку самостоятельно, \n"
                      f"сообщите, пожалуйста, нам об ошибке через форму обратной связи.", category='error')
            else:                
                flash((f"Книга успешно добавлена вами в каталог под номером #{res[0]['result']}. \n"                       
                       f"Запишите этот номер в книгу на 17ой странице. \n"
                       f'Благодаря этому любой читатель книги всегда будет знать, кому она принадлежит. \n'
                       f"Спасибо, что поддерживаете активность в нашем проекте."), category='success')

        return render_template('add-book.html', title="Регистрация новой книги",
                               menu=callproc('[dbo].[sp_get_menu]', ()), genres=callproc('[dbo].[sp_get_genres]', ()),
                               user=session['userLogged'].split('@')[0])
    else:
        return redirect(url_for('login'))

@app.route('/req_take_book/<string:book_code>/<string:owner>', methods=["GET"])
def req_take_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 2, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка запроса на выдачу книги с кодом #{book_code}. \n"
                  f"Убедитесь, что у вас нет на руках других книг, и что вы не являетесь владельцем этой книги. \n"
                  f"Кроме этого, возможно, что книга уже выдана или запрошена другим пользователем:) \n"
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Читателем запрошена выдача книги с кодом #{book_code}. "
                               f"Свяжитесь с читатателем по адресу эл.почты {session['userLogged']} "
                               f"для очной передачи книги. "
                               f"ПОСЛЕ факта передачи книги читателю подтвердите, пожалуйста, выдачу книги в личном кабинете.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success')
            flash((f"Книга с кодом #{book_code} успешно запрошена у владельца. \n"
                   f"Мы сообщили ему об этом по эл. почте. \n"
                    f'Ожидайте, пожалуйста, когда владелец свяжется с вами для передачи книги.'), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    
@app.route('/unreq_take_book/<string:book_code>/<string:owner>', methods=["GET"])
def unreq_take_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 3, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка при отмене запроса на выдачу книги с кодом #{book_code}. \n"                  
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Читателем  {session['userLogged'].split('@')[0]} отменён запрос на выдачу книги с кодом #{book_code}. С вашей стороны действий не требуется.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success')            
            flash((f"Отменен запрос на выдачу книги с кодом #{book_code}."
                    f'Владелец книги был уведомлен об этом по эл. почте. '), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))


@app.route('/take_book/<string:book_code>/<string:reader>', methods=["GET"])
def take_book(book_code, reader):    
    if 'logged_in' in session:        
        res = callproc('[dbo].[sp_change_status]', (book_code, 4, session['userLogged']))        
        if not res[0]['result']:
            flash(f"Ошибка при выдаче книги под номером #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Выдача книги с кодом #{book_code} подтверждёна владельцем {session['userLogged'].split('@')[0]}. "
                               f"С вашей стороны действий не требуется."
                               f"Книгу необходимо вернуть в установленный срок (см. Личный кабинет)",
                               [f'{reader}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления читателю книги на адрес эл.почты {reader}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено читателю книги на адрес эл.почты {reader}@tele2.ru."
                      , category='success') 
            flash((f"Книга под номером #{book_code} успешно выдана читателю. \n"
                    f"Спасибо, что поддерживаете активность в нашем проекте."), category='success')
        
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    
@app.route('/req_extend_book/<string:book_code>/<string:owner>', methods=["GET"])
def req_extend_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 5, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка при запросе на продление книги с кодом #{book_code} у владельца. \n"                  
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Поступил запрос от читателя {session['userLogged'].split('@')[0]} на продление срока возврата книги с кодом #{book_code}. "
                               f"Подтвердите запрос или откажите читателю в продлении книги в личном кабинете.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success')  
            flash((f"Запрошено продление срока возрата книги с кодом #{book_code}. \n"
                   f"Мы сообщили владельцу об этом по эл. почте. \n"
                    f'Ожидайте, пожалуйста, когда владелец примет решение о продлении книги или об отказе в продлении.'), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    

    
@app.route('/unreq_extend_book/<string:book_code>/<string:owner>', methods=["GET"])
def unreq_extend_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 6, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка при отмене запроса на продление книги с кодом #{book_code}. \n"                  
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Читателем {session['userLogged'].split('@')[0]} отменён запрос на продление срока возврата книги с кодом #{book_code}. "
                               f"С вашей стороны действий не требуется.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success')  
            flash((f"Отменен запрос на продление книги с кодом #{book_code}. \n"
                    f'Владелец книги был уведомлен об этом по эл. почте. '), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    

@app.route('/extend_book/<string:book_code>/<string:reader>', methods=["GET"])
def extend_book(book_code, reader):    
    if 'logged_in' in session:        
        res = callproc('[dbo].[sp_change_status]', (book_code, 7, session['userLogged']))        
        if not res[0]['result']:
            flash(f"Ошибка при подтверждении продления срока возврата книги с кодом #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Запрос на продление книги с кодом #{book_code} подтверждён владельцем {session['userLogged'].split('@')[0]}. "
                               f"Книгу необходимо вернуть в новый установленный срок (см. Личный кабинет). "
                               f"С вашей стороны действий не требуется.",
                               [f'{reader}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления читателю книги на адрес эл.почты {reader}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено читателю книги на адрес эл.почты {reader}@tele2.ru."
                      , category='success') 
            flash((f"Книга с кодом #{book_code} успешно продлена. \n"
                   f'Читатель книги был уведомлен об этом по эл. почте.\n'
                   f"Спасибо, что поддерживаете активность в нашем проекте. \n"), category='success')
        
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    
@app.route('/unextend_book/<string:book_code>/<string:reader>', methods=["GET"])
def unextend_book(book_code, reader):    
    if 'logged_in' in session:        
        res = callproc('[dbo].[sp_change_status]', (book_code, 8, session['userLogged']))        
        if not res[0]['result']:
            flash(f"Ошибка при отказе в продлении срока возврата книги с кодом #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Запрос на продление книги с кодом #{book_code} отклонён владельцем {session['userLogged'].split('@')[0]}. "
                               f"С вашей стороны действий не требуется. "
                               f"Книгу необходимо вернуть в установленный ранее срок (см. Личный кабинет)",
                               [f'{reader}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления читателю книги на адрес эл.почты {reader}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено читателю книги на адрес эл.почты {reader}@tele2.ru."
                      , category='success') 
            flash((f"Читателю отказано в продлении книги под номером #{book_code}. \n"
                   f'Читатель книги был уведомлён об этом по эл. почте.\n'
                   f"Мы с пониманием относимся к вашему решению и знаем, что вы предварительно взвесили все за и против:)\n"), 
                   category='success')
        
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    
@app.route('/req_return_book/<string:book_code>/<string:owner>', methods=["GET"])
def req_return_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 9, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка при запросе на организацию возврата книги с кодом #{book_code}. \n"                  
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Поступил запрос от читателя на организацию возврата вашей книги с кодом #{book_code}. "
                               f"Свяжитесь с читатателем по адресу эл.почты {session['userLogged']} "
                               f"для очной передачи книги. "
                               f"ПОСЛЕ факта получения книги подтвердите возврат книги в личном кабинете.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success') 
            flash((f"Отправлен запрос владельцу книги на организацию возврата книги с кодом #{book_code}. \n"
                   f"Мы сообщили владельцу об этом по эл. почте. \n"
                    f'Ожидайте, пожалуйста, когда владелец свяжется с вами для очной передачи книги'), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))
    
@app.route('/unreq_return_book/<string:book_code>/<string:owner>', methods=["GET"])
def unreq_return_book(book_code, owner):    
    if 'logged_in' in session:   
        res = callproc('[dbo].[sp_change_status]', (book_code, 10, session['userLogged']))
        if not res[0]['result']:
            flash(f"Ошибка при отмене запроса к владельцу на организацию возврата книги с кодом #{book_code}. \n"                  
                  f"Если не удается выявить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Читателем {session['userLogged'].split('@')[0]} отменён запрос на организацию возврата книги с кодом #{book_code}. "
                               f"С вашей стороны действий не требуется.",
                               [f'{owner}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления владельцу книги на адрес эл.почты {owner}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено владельцу книги на адрес эл.почты {owner}@tele2.ru."
                      , category='success') 
            flash((f"Отменен запрос на организацию возврата книги с кодом #{book_code}. \n"
                    f'Владелец был будет уведомлен об этом по эл. почте. '), category='success')    
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))


@app.route('/return_book/<string:book_code>/<string:reader>', methods=["GET"])
def return_book(book_code, reader):    
    if 'logged_in' in session:        
        res = callproc('[dbo].[sp_change_status]', (book_code, 11, session['userLogged']))        
        if not res[0]['result']:
            flash(f"Ошибка при подтверждении факта возврата книги с кодом #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                    f"сообщите, пожалуйста, нам об этом через форму обратной связи.", category='error')
        else:
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Возврат книги с кодом #{book_code} подтверждён владельцем {session['userLogged'].split('@')[0]}. "
                               f"С вашей стороны дополнительных действий не требуется. "
                               f"Спасибо, что участвуете в проекте! Возращайтесь снова!",
                               [f'{reader}@tele2.ru'])
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомления читателю книги на адрес эл.почты {reader}@tele2.ru. \n"
                      f"Обратитесь, пожалуйста, к организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомление успешно отправлено читателю книги на адрес эл.почты {reader}@tele2.ru."
                      , category='success') 
            flash((f"Книга с кодом #{book_code} успешно позвращена владельцу. \n"                   
                   f"Спасибо, что поддерживаете активность в нашем проекте. \n"), category='success')
           
           #отправка рассылки всем подписчикам книги
            addressees = []
            emails = callproc('[dbo].[sp_get_book_followers]', (book_code,)) 
            for email in emails:
                addressees.append(email['email'])
            is_sent = send_email(f'Статус книги #{book_code}',
                               f"Возврат книги с кодом #{book_code} подтверждён владельцем {session['userLogged'].split('@')[0]}. "
                               f"Книга снова доступна для выдачи в каталоге проекта."                               
                               f"Поспеши, если книга тебе ещё интересна! Отменить подписку на книгу можно в личном кабинете. ",
                               addressees)
            if not is_sent[0]:
                flash(f"Ошибка при отправке уведомлений подписчикам о доступности книги. \n"
                      f"Сообщите, пожалуйста, об ошибке организаторам проекта через форму обратной связи.", category='error')                
            else:
                flash(f"Уведомления о доступности книги успешно отправлены подписчикам."
                      , category='success') 
        
        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))


@app.route('/subscribe_book/<string:book_code>', methods=["GET"])
def subscribe_book(book_code):
    if 'logged_in' in session:
        res = callproc('[dbo].[sp_add_new_subscription]', (book_code, session['userLogged']))  
        if not res[0]['result']:
            flash(f"Ошибка при подписке на книгу с кодом #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                  f"сообщите, пожалуйста, нам об ошибке через форму обратной связи.", category='error')
        else:
            msg = (f"Оформлена новая подписка на книгу с кодом #{book_code}. \n"
                   f'Теперь мы будем сообщать вам, если книга возвращается владельцу и снова доступна для выдачи.')            

        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))


@app.route('/unsubscribe_book/<string:book_code>', methods=["GET"])
def unsubscribe_book(book_code):
    if 'logged_in' in session:
        res = callproc('[dbo].[sp_close_subscription]', (book_code, session['userLogged'], 1))  
        if not res[0]['result']:
            flash(f"Ошибка при отмене подписки на книгу с кодом #{book_code}. \n"
                  f"Если не удается устранить ошибку самостоятельно, \n"
                  f"сообщите, пожалуйста, нам об ошибке через форму обратной связи.", category='error')
        else:
            flash((f"Подписка на книгу с кодом #{book_code} прекращена. \n"
                   f"Теперь мы НЕ будем сообщать вам, если книга возвращается владельцу и снова доступна для выдачи."), 
                   category='success')

        return redirect(url_for('lk'))
    else:
        return redirect(url_for('login'))


@app.route("/rules", methods=["GET"])
def rules():
    if 'logged_in' in session:
        
        return render_template('rules.html', title='Правила проекта "Книжный перекрёсток"',
                               rules=callproc('[dbo].[sp_get_rules]', ()),
                               menu=callproc('[dbo].[sp_get_menu]', ()),
                               user=session['userLogged'].split('@')[0])
    else:
        return redirect(url_for('login'))


@app.route("/lk", methods=["POST", "GET"])
def lk():
    if 'logged_in' in session:        
        return render_template('lk.html', title='Личный кабинет',
                               # True - т.е. для отображения в ЛК, а не на главной
                               taken_books=callproc('[dbo].[sp_get_taken2me_books]', (session['userLogged'],)),
                               subscriptions=callproc('[dbo].[sp_get_my_subscriptions]', (session['userLogged'],)),
                               book_log=callproc('[dbo].[sp_get_my_forms_log]', (session['userLogged'],)),
                               my_books=callproc('[dbo].[sp_get_my_books]', (session['userLogged'],)),
                               menu=callproc('[dbo].[sp_get_menu]', ()),
                               user=session['userLogged'].split('@')[0])
    else:
        return redirect(url_for('login'))

# для ввода кода подтверждения отправляй код на почту
# и перенаправляй на спец страницу с формой для ввода полученного кода


@app.route("/login", methods=["POST", "GET"])
def login():
    if 'logged_in' in session:
        return redirect(url_for('rules'))
    form = LoginForm()
    if form.validate_on_submit():        
        email = form.email.data.lower().strip()
        if email.split('@')[1] == 'tele2.ru':
            session['userLogged'] = email            
            code = random.randint(1000, 9999)  # генерация случайного кода
            session['code'] = code  # сохранение кода в сессии
            is_sent = send_email('Код подтверждения',
                               f'Ваш код подтверждения: {code}',
                               [email])
            if not is_sent[0]:
                flash(f"Ошибка при отправке кода подтверждения: {is_sent[1]}. "
                      f"Если не удается устранить ошибку самостоятельно, \n"
                      f"обратитесь, пожалуйста, к организаторам проекта.", category='error')
                return redirect(url_for('login'))
            else:
                flash(f"Код подтверждения успешно отправлен на адрес электронной почты {email}. "
                      f"Проверьте вашу почту и введите полученный код в поле ниже.", category='success')
                return render_template('verify_code.html', title="Ввод кода подтверждения", menu=callproc('[dbo].[sp_get_menu]', ()))
        else:
            flash(f"Не верно указан домен (@tele2.ru) корпоративной эл. почты (пример, ivan.ivanov@tele2.ru). "
                  f"Если не удается устранить ошибку самостоятельно, \n"
                  f"обратитесь, пожалуйста, к организаторам проекта.", category='error')
            return redirect(url_for('login'))
    else:
        return render_template('login.html', title="Авторизация участника", menu=callproc('[dbo].[sp_get_menu]', ()), form=form)

# обработка ввода кода подтверждения
@app.route('/verify_code', methods=["POST", "GET"])
def verify_code():
    if 'logged_in' in session:
        return redirect(url_for('rules'))
        
    if request.method == 'POST':
        code = request.form['code']
        if 'code' in session and str(session['code']) == code:
            add_user = callproc('[dbo].[sp_add_new_user]', (session['userLogged'],))
            #Если 1, то новый пользователь добавлен, если 0 - уже зарегистрирован
            if add_user[0]['result']: 
                # сохранение информации о входе в сессию
                session['logged_in'] = True
                return redirect(url_for('rules'))
            else:
                # сохранение информации о входе в сессию
                session['logged_in'] = True
                return redirect(url_for('index'))        
        else:
            flash(f"Код подтверждения указан не верно. Попробуйте ввести повторно. "
                  f"Если не удается устранить ошибку самостоятельно, "
                  f"обратитесь, пожалуйста, к организаторам проекта.",
                  category='error')
            return redirect(url_for('verify_code'))
    else:
        return render_template('verify_code.html', title="Ввод кода подтверждения", menu=callproc('[dbo].[sp_get_menu]', ()))


@app.route("/contact", methods=["POST", "GET"])
def contact():
    if 'logged_in' in session:        
        if request.method == "POST":
            msg = request.form['message'].strip()
            res = callproc('[dbo].[sp_add_new_fb_support]', (session['userLogged'], msg))
            if not res[0]['result']:
                flash(
                    f"Ошибка отправки обращения.", category='error')
            else:
                flash((f"Обращение #{res[0]['result']} принято в работу. "
                       f"Ожидайте ответа от организаторов на адрес вашей эл. почты: {session['userLogged']}"), category='success')

        return render_template('contact.html', title="Обратная связь", menu=callproc('[dbo].[sp_get_menu]', ()),
                               feedbacks=callproc('[dbo].[sp_get_fb_support]', (session['userLogged'],)),
                               user=session['userLogged'].split('@')[0], check_admin=callproc('[dbo].[sp_get_is_admin]', (session['userLogged'],)))
    else:
        return redirect(url_for('login'))


@app.route('/close_feedback/<int:fb_id>', methods=["GET"])
def close_feedback(fb_id):
    if 'logged_in' in session:        

        res = callproc('[dbo].[sp_close_fb_support]', (fb_id, ))
        if not res[0]['result']:
            flash(f"Ошибка при закрытии обращения #{fb_id}.", category='error')
        else:
            flash(f'Обращение #{fb_id} закрыто.', category='success')

        return redirect(url_for('contact'))
    else:
        return redirect(url_for('login'))


@app.route("/exit", methods=["GET"])
def exit():
    session.clear()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(error):
    return render_template('page404.html', title='Страница не найдена', menu=callproc('[dbo].[sp_get_menu]', ())), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template('page403.html', title='Доступ к информации ограничен, т.к. вы не являетесь администратором ресурса.',
                           menu=callproc('[dbo].[sp_get_menu]', ())), 403

if __name__ == "__main__":
    app.run(host='0.0.0.0') 