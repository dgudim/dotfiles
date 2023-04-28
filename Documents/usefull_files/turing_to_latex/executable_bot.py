#!/usr/bin/python

import telebot
import time
import os
import pydot
from telebot import types
import requests

import glob
import shutil

from autogen import gen

API_TOKEN = "5980932188:AAHMgklvSlNjRMsSrJuSqfnDoe4bhNgdNng"

bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, text="Hello, {0.first_name}! I am your report generator bot"
                     .format(message.from_user))
    bot.send_message(message.chat.id, text="""
The procedure is as follows:
❖ 1. You send me your turing machine code and some info about the machine (start by typing /generate_tex)
❖ 2. I send you latex file with most of the stuff already done
❖ 3. You edit this file to your liking (fill in the title page, etc)
❖ 4. You send me this file back and i give you the report in pdf (type /gen_pdf)
""")
    
@bot.message_handler(commands=['generate_tex'])
def gen_latex(message):
    markup = types.ReplyKeyboardRemove(selective=False)
    msg = bot.send_message(message.chat.id, text="Please provide the language of the input string, eg: a,b or a,b,c", reply_markup=markup)
    bot.register_next_step_handler(msg, request_tape_lang)
    
def request_tape_lang(message, prev_msg=None):
    
    src_letters = [];
    valid = True
    
    message = message if prev_msg is None else prev_msg;
    
    for letter in message.text.split(","):
        letter = letter.strip();
        if len(letter) > 1 or len(letter) == 0:
            bot.send_message(message.chat.id, text=f"'{letter}' is not a valid letter, try again")
            valid = False
        src_letters.append(letter);
    source_letters_raw = dict.fromkeys(src_letters);  
     
    if valid:
        msg = bot.send_message(message.chat.id, text="Please provide the language of the tape, eg: a,b,_ or a,b,c,_")
        bot.register_next_step_handler(msg, request_accept_state, message, source_letters_raw)
    else:
        gen_latex(message)

def request_accept_state(message, prev_msg, source_letters_raw):
    
    tape_letters = [];
    valid = True
    
    for letter in message.text.split(","):
        letter = letter.strip();
        if len(letter) > 1 or len(letter) == 0:
            bot.send_message(message.chat.id, text=f"'{letter}' is not a valid letter, try again")
            valid = False
        tape_letters.append(letter);
    tape_letters_raw = dict.fromkeys(tape_letters);  
    
    if valid:
        msg = bot.send_message(message.chat.id, text="Please provide the accept state eg: halt-accept")
        bot.register_next_step_handler(msg, request_reject_state, source_letters_raw, tape_letters_raw)
    else:
        request_tape_lang(message, prev_msg);


def request_reject_state(message, source_letters_raw, tape_letters_raw):
    
    accept_state = message.text.strip();
    
    msg = bot.send_message(message.chat.id, text="Please provide the reject state eg: halt-reject, if there is no reject state send . ")
    bot.register_next_step_handler(msg, request_starting_state, source_letters_raw, tape_letters_raw, accept_state)

def request_starting_state(message, source_letters_raw, tape_letters_raw, accept_state):
    
    reject_state = "" if message.text.strip() == "." else message.text.strip();
    
    msg = bot.send_message(message.chat.id, text="Please provide the starting state eg: 0")
    bot.register_next_step_handler(msg, input_name, source_letters_raw, tape_letters_raw, accept_state, reject_state)

def input_name(message, source_letters_raw, tape_letters_raw, accept_state, reject_state):
    
    starting_state = message.text.strip();
    
    msg = bot.send_message(message.chat.id, text="Please provide your name and surname")
    bot.register_next_step_handler(msg, check_data, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state)

def check_data(message, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state):
    
    student = message.text.strip();
    
    bot.send_message(message.chat.id, text="Please check your data")
    bot.send_message(message.chat.id, text=f"""
❖ Source letters: {source_letters_raw.keys()}
❖ Tape letters: {tape_letters_raw.keys()}
                     
❖ Starting state: {starting_state}
❖ Accept state: {accept_state}
❖ Reject state: {reject_state}
                     
❖ Student: {student}
                     """)
    
    markup = types.ReplyKeyboardMarkup(row_width=2)
    itembtn1 = types.KeyboardButton('all good')
    itembtn2 = types.KeyboardButton('retry')
    markup.add(itembtn1, itembtn2)
    msg = bot.send_message(message.chat.id, "Everything good?", reply_markup=markup)
    bot.register_next_step_handler(msg, request_file, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student)

def request_file(message, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student):
    
    if message.text == "all good":
        markup = types.ReplyKeyboardRemove(selective=False)
        msg = bot.send_message(message.chat.id, "Please send me your turing machine source code in a file", reply_markup=markup)
        bot.register_next_step_handler(msg, check_file, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student)
    else:
        gen_latex(message);

def check_file(message, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student):
    if message.document is not None and message.document.file_id is not None:
        uniquename = str(time.time());
        file_info = bot.get_file(message.document.file_id)
        
        bot.send_message(message.chat.id, "Trying to generate a latex file, please wait")
        
        with requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path)) as r:
            r.raise_for_status()
            with open(f"{uniquename}.txt", 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
        try:
            tex, diagram = gen(source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student, uniquename);
            doc = open(tex, 'rb')
            diagr = open(diagram, 'rb')
            bot.send_message(message.chat.id, "Here are your files");
            bot.send_document(message.chat.id, doc)
            bot.send_document(message.chat.id, diagr)
            doc.close();
            diagr.close();
            
        except Exception as e:
            bot.send_message(message.chat.id, f"An error ocurred: {e}");
            
    else:
        msg = bot.send_message(message.chat.id, "You did not send a file");
        bot.register_next_step_handler(msg, check_file, source_letters_raw, tape_letters_raw, accept_state, reject_state, starting_state, student)
        

@bot.message_handler(commands=['gen_pdf'])
def gen_pdf(message):
    if message.document is not None and message.document.file_id is not None:
        uniquename = str(time.time());
        file_info = bot.get_file(message.document.file_id)
        
        bot.send_message(message.chat.id, "Trying to generate a pdf file, please wait")
        
        os.mkdir(uniquename)
        
        for jpgfile in glob.iglob(os.path.join(".", "*.png")):
            shutil.copy(jpgfile, uniquename)
            
        filepath = f"{uniquename}/{uniquename}";
        
        with requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path)) as r:
            r.raise_for_status()
            with open(f"{filepath}.tex", 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
        try:
            os.system(f"cd {uniquename} && pdflatex -synctex=1 -interaction=nonstopmode {uniquename}.tex")  
            os.system(f"cd {uniquename} && bibtex {uniquename}")  
            os.system(f"cd {uniquename} && pdflatex -synctex=1 -interaction=nonstopmode {uniquename}.tex")  
            doc = open(f"{filepath}.pdf", 'rb')
            bot.send_message(message.chat.id, "Here is your file");
            bot.send_document(message.chat.id, doc)
            doc.close()
        except Exception as e:
            bot.send_message(message.chat.id, f"An error ocurred: {e}");
            
    else:
        msg = bot.send_message(message.chat.id, "You did not send a file");
        bot.register_next_step_handler(msg, gen_pdf)



bot.polling(none_stop=True)
