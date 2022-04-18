from telebot.async_telebot import AsyncTeleBot
from telebot import types
import asyncio
import pandas as pd
import os
from ping3 import ping
from datetime import datetime, timedelta
import logging

TOKEN = 'Your bot token'
bot = AsyncTeleBot(token=TOKEN)

logging.basicConfig(
    level=logging.INFO,
    filename="bot_logs.log",
    format="%(asctime)s - %(module)s - %(levelname)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S',
)

commands = {'/start': 'start using the bot and print commands',
            '/help': 'print the same as start',
            '/add_server': 'let\'s use this to add server to spectate it',
            '/servers_list': 'it will print list of servers which you have added earlier to spectate',
            '/del_server': 'using to del the server from the spectating list',
            '/clear_list_of_servers': 'it will use del_server for all_servers that you have added before',
            }



def create_df():
    if 'clients.csv' in os.listdir():
        clients = pd.read_csv('clients.csv')
    else:
        clients = pd.DataFrame([], columns=['chat_id', 'server'])
    if 'servers.csv' in os.listdir():
        servers = pd.read_csv('servers.csv')
    else:
        servers = pd.DataFrame([], columns=['server', 'broken'])
    return clients, servers


def pinger(server):
    try:
        response = ping(server)
        if type(response) == float:
            return True
        else:
            return False
    except TimeoutError:
        return False


@bot.message_handler(commands=['start', 'help'])
async def start(message):
    global commands
    text_to_print = '''Hello I'm a bot for checking avaliabilities of servers.
My creator will be glad to see that i'm usefull for you.

Description:
Bot will ping servers every 10 seconds and will send message to you if server has become unavailable.
If server is not unavailable, bot will send message about this every hour, then if server will become available again,
bot will send a message to you.

If you need to stop using bot, please use the command 
/clear_servers_list

My commands : \n'''
    for key in commands:
        text_to_print += f'{key} : {commands[key]} \n'
    await bot.send_message(message.chat.id, text_to_print)


@bot.message_handler(commands=['servers_list'])
async def servers_list(message):
    servers_for_person = clients.loc[clients.chat_id == message.chat.id, 'server'].to_list()
    if len(servers_for_person) == 0:
        await bot.send_message(message.chat.id, 'Your list of servers is empty.')
    else:
        message_to_send = 'There are servers that we are checking for you: \n'
        for server in servers_for_person:
            message_to_send += server + '\n'
        await bot.send_message(message.chat.id, message_to_send)


@bot.message_handler(commands=['add_server'])
async def add_server(message):
    global clients
    global servers
    to_add = message.text.split()[1]
    if pinger(to_add):
        if to_add not in clients.loc[clients.chat_id == message.chat.id, 'server'].values:
            clients = pd.concat([clients,
                                 pd.DataFrame([[message.chat.id, to_add]], columns=clients.columns)],
                                ignore_index=True)
            await bot.send_message(message.chat.id, f'Server is added: {to_add}')
        else:
            await bot.send_message(message.chat.id, f'This server has been added earlier: {to_add}')
        if to_add not in servers['server'].values:
            servers = pd.concat([servers,
                                 pd.DataFrame([[to_add, False]], columns=servers.columns)],
                                ignore_index=True)
        clients.to_csv('clients.csv', index=False)
        servers.to_csv('servers.csv', index=False)
    else:
        await bot.send_message(message.chat.id, f'We can\'t ping this server now: {to_add}')


@bot.message_handler(commands=['del_server'])
async def del_server(message):
    to_del = message.text.split()[1]
    if to_del in clients.loc[clients.chat_id == message.chat.id, 'server'].values:
        if len(clients.loc[clients.server == to_del, 'chat_id'].to_list()) == 1:
            servers.drop(servers.loc[servers.server == to_del].index, inplace=True)
            servers.to_csv('servers.csv')
        clients.drop(clients.loc[(clients.chat_id == message.chat.id) & (clients.server == to_del)].index, inplace=True)
        clients.to_csv('clients.csv', index=False)
        await bot.send_message(message.chat.id, f'Server is removed: {to_del}')
    else:
        await bot.send_message(message.chat.id, 'We didn\'t find this server in your list.')


@bot.message_handler(commands=['clear_list_of_servers'])
async def clear_list_ask(message):
    keyboard = types.InlineKeyboardMarkup()
    key_yes = types.InlineKeyboardButton('Yes', callback_data='yes')
    key_no = types.InlineKeyboardButton('No', callback_data='no')
    keyboard.add(key_yes)
    keyboard.add(key_no)
    await bot.send_message(message.chat.id,
                           'Are you sure that you want to clear the list of servers?',
                           reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
async def clear_list(call):
    if call.data == 'yes':
        client_servers = clients.loc[clients.chat_id == call.message.chat.id, 'server']
        to_drop = clients.loc[clients.chat_id == call.message.chat.id].index
        if len(to_drop) == 0:
            await bot.send_message(call.message.chat.id, 'Your list of servers is empty')
        else:
            for server in client_servers:
                if len(clients.loc[clients.server == server, 'chat_id'].to_list()) == 1:
                    servers.drop(servers.loc[servers.server == server].index, inplace=True)
                    servers.to_csv('servers.csv')
                servers.to_csv('servers.csv', index=False)
            clients.drop(to_drop, inplace=True)
            clients.to_csv('clients.csv', index=False)
            await bot.send_message(call.message.chat.id, 'Your list of servers is cleared')


async def server_unavailable(server):
    for chat_id in clients.loc[clients.server == server, 'chat_id'].to_list():
        await bot.send_message(chat_id, f'{server} is not available!')


async def server_available_again(server):
    for chat_id in clients.loc[clients.server == server, 'chat_id'].to_list():
        await loop.create_task(bot.send_message(chat_id, f'This server {server} is available again!'))


async def main():
    global servers
    while True:
        for server in set(servers.server.to_list()):
            ping_result = pinger(server)
            if not ping_result:
                if servers.loc[servers.server == server, 'broken'].values[0] == False or \
                        datetime.now() - servers.loc[servers.server == server, 'broken'].values[0] > timedelta(hours=1):
                    await server_unavailable(server)
                    servers.loc[servers.server == server, 'broken'] = datetime.now()
                    servers.to_csv('servers.csv', index=False)

            else:
                if servers.loc[servers.server == server, 'broken'].values[0]:
                    await server_available_again(server)
                    servers.loc[servers.server == server, 'broken'] = False
                    servers.to_csv('servers.csv', index=False)

            await asyncio.sleep(0.3)
        await asyncio.sleep(10)


clients, servers = create_df()
loop = asyncio.get_event_loop()
tasks = [main(), bot.polling(interval=1, none_stop=True)]
loop.run_until_complete(asyncio.wait(tasks))
