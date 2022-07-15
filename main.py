from collections import defaultdict
from telegram.ext import Application, ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters, PicklePersistence
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from datetime import datetime
from contextlib import suppress
from web3 import Web3
from web3._utils.filters import Filter
import json, asyncio, time, random, threading
import requests as req

task = None
# Determines whether the bot is required to track SHEBA purchases
tracking = False
# Determines whether an ongoing competition is occurring at this moment
competition = {'on': False, 'highest': False, 'values': [60, 0.01, 1, 2.0, 0, 0], 'idx': None, 'best': { 'buy' : defaultdict(float), 'txn' : [] }, 'time' : { 'init': None, 'end': None, 'posix': None }, 'id' : 0, 'winners':{'all' : [], } }
# The buy gif/sticker/image
buy_graphic = { 'graphic' :  [None, None, None], 'idx' : None }
# The buy emoji
buy_emoji = '🟢'
# The buy step
buy_step = 10
# Stages
START_PAGE, COMP_PAGE, COMP, GIF, EMOJI, STEP = range(6)
# Callback data
ONE, TWO, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE = range(9)
# Start/Help message
INITIAL_MESSAGE = "Welcome to BestBuyBot ✅\n\n- I can also act as a normal buy bot without a biggest buy contest\n\n- To begin, make me (@BestBuyTechBot) an Admin in your group\n\n- Type /settings to show all available easy to use settings\n\n- Type /comp to view the current buy contest leaderboard\n\n- Type /winners to view all previous buy contests' winners"
# The EIP20 Application Binary Interface
EIP20_ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"spender","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"},{"constant":true,"inputs":[{"internalType":"address","name":"_owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"getOwner","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"internalType":"address","name":"sender","type":"address"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transferFrom","outputs":[{"internalType":"bool","name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"}]')
# The BSC RPC url to use the Binance Smart Chain (BSC) Mainnet
BNB_RPC = 'https://bsc-dataseed.binance.org/'
w3 = Web3(Web3.HTTPProvider(BNB_RPC))
# SHEBA/BNB Pancakeswap V2 Pair Contract
pair = w3.eth.contract(address='0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', abi=EIP20_ABI)
# Create an event filter which tracks all BNB transactions going to the SHEBA/BNB pair
tx_filter = pair.events.Transfer.createFilter(fromBlock="latest", argument_filters={'to':'0x874aF1AeE95d25b9D8BD340f3FED11D423B568B7'})
# Create a pickled save file
bot_per = PicklePersistence(filepath='pickled_chat_data')
# Create the Application object and pass it your bot's token
application = Application.builder().token("5368823457:AAGloHCWzWjzLPi6XenSVn-nj86WH1F-Xkg").persistence(persistence=bot_per).build()

class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

async def end_competition():
    results = None
    if len(competition['best']['buy']) > 0 or len(competition['best']['txn']) > 0:
        if competition['highest']:
            buy = {k: v for k, v in sorted(competition['best']['buy'].items(), key=lambda item: item[1])}
            for i in reversed(range(3)):
                possible = len(buy.values()) > i
                if not possible:
                    continue
                else:
                    results = list(buy.items())[-(i+1):]
                    break
            competition['winners']['all'].append([results[0][0], competition['values'][2]])
        else:
            length = len(competition['best']['txn'])
            idx = [random.randint(0, length - 1)]
            results = [competition['best']['txn'][idx[0]]]
            for i in range(2):
                possible = length > i + 1
                if not possible:
                    break
                else:
                    new_idx = random.randint(0, length - 1)
                    while new_idx in idx:
                        new_idx = random.randint(0, length - 1)
                    results.append(competition['best']['txn'][new_idx])
            competition['winners']['all'].append([results[0], competition['values'][2]])
        competition['winners']['last'] = results
        message = await application.bot.send_message(chat_id=competition['id'], text='<b>🏁 Buy Competition Finished\n\n🕓 Start at %s\n🏁 End %s\n⏫ Minimum Buy %s\n\n%s\n\n🎊 Congrats to %s</b>' % (competition['time']['init'].strftime("%H:%M:%S"), competition['time']['end'].strftime("%H:%M:%S"), competition['values'][1], winners(), results[0][0] if competition['highest'] else results[0]), parse_mode=constants.ParseMode.HTML)
    else:
        message = await application.bot.send_message(chat_id=competition['id'], text='<b>🏁 Buy Competition Finished\n\n🕓 Start at %s\n🏁 End %s\n⏫ Minimum Buy %s\n➡️ There was no buyer in competition</b>' % (competition['time']['init'].strftime("%H:%M:%S"), competition['time']['end'].strftime("%H:%M:%S"), competition['values'][1]), parse_mode=constants.ParseMode.HTML)
    await message.pin()
    competition['on'] = False

def winners() -> str:
    """ Creates the top-3 ranking for a competition which has finished.

    Returns:
        str: The three best winners and the amount of BNB they spent on buying.
    """
    medals = {0:'🥇', 1: '🥈', 2: '🥉'}
    winners = ''
    for i in range(len(competition['winners']['last'])):
        addr = competition['winners']['last'][i][0] if competition['highest'] else competition['winners']['last'][i]
        amnt = competition['winners']['last'][i][1] if competition['highest'] else ''
        winners += medals[i] + ' ' + addr[:6] +'...'+ addr[-4:]+ (('➖ %s BNB' % amnt) if competition['highest'] else '') +  '\n'

    return winners
    
async def log_loop(event_filter : Filter, poll_interval: int) -> None:
    """Runs an infinite loop which seeks new SHEBA transactions and updates the group for each transaction. 

    Args:
        event_filter (Filter): A Web3.py Filter object which determines the type of transaction to look out for
        poll_interval (int): The delay between each call attempting to fetch new transactions (in seconds)
    """
    global task
    while True:
        for event in event_filter.get_new_entries():
            amount = int(event['args']['value']) / 1e18
            frm = req.get('https://api.bscscan.com/api?module=account&action=txlistinternal&txhash=0xd592785d74f9fdf22ce6258128050627e997cda3cd717287f255a5764814ba25&apikey=IFYW4RN4AFPWV7PAWX6B6B4EBJP9VZYU1Y').json()["result"][1]["to"]
            if competition['on'] and amount >= competition['values'][1]:
                if competition['highest']:
                    competition['best']['buy'][frm] += amount
                elif not competition['highest']:
                    competition['best']['txn'].append(frm)
            # Fetch and compute the amount in dollars
            price = req.get('https://api.pancakeswap.info/api/v2/tokens/0x08762be6631bef12efb750ff276e2e5095957afb').json()['data']
            dollars = amount * float(price['price']) / float(price['price_BNB'])
            # Evaluate whether the buyer is a new holder
            usr_bal = float(req.get('https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress=0x08762be6631BeF12Efb750ff276e2e5095957AfB&address=%s&tag=latest&apikey=IFYW4RN4AFPWV7PAWX6B6B4EBJP9VZYU1Y' % frm).json()["result"]) / 1e18
            difference = (usr_bal * float(price['price_BNB'])) - amount
            new = abs(difference) <= 0.000001
            #Compute marketcap
            zero_bal = float(req.get('https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress=0x08762be6631BeF12Efb750ff276e2e5095957AfB&address=0x000000000000000000000000000000000000dEaD&tag=latest&apikey=IFYW4RN4AFPWV7PAWX6B6B4EBJP9VZYU1Y').json()["result"]) / 1e18
            total_sup = float(req.get('https://api.bscscan.com/api?module=stats&action=tokensupply&contractaddress=0x08762be6631BeF12Efb750ff276e2e5095957AfB&apikey=IFYW4RN4AFPWV7PAWX6B6B4EBJP9VZYU1Y').json()["result"]) / 1e18
            mcap = (total_sup - zero_bal) * float(price['price'])
            buy_message="<b>%s</b> Buy!\n%s\n\n💸 %s BNB ($%s)\n👤 Buyer %s\n%s\n💰 Market Cap <b>$%s</b>\n%s\n\n📈 <a href='https://dexscreener.com/bsc/0x08762be6631bef12efb750ff276e2e5095957afb'>Chart</a> | <a href='https://bscscan.com/tx/%s'>Buy txn</a>" % (price['name'],''.join([buy_emoji for _ in range(int(dollars // buy_step) if int(dollars // buy_step) > 1 else 1)]), amount, dollars, frm, "🔥 <b>New Holder</b>" if new else "⏫ Position <b>+{}%</b>".format(abs(amount * 100 / difference)), round(mcap, 2), "🏁 <b>Buy competition ends in %s /comp\n🎖 Winning prize %s</b>" % (get_dif(), prize_str()) if competition['on'] else "/comp", event['transactionHash'].hex())
            for id in list(application.chat_data.keys()):
                await send_graphic(id)
                await application.bot.send_message(chat_id=id, text=buy_message, parse_mode=constants.ParseMode.HTML)
        time.sleep(poll_interval)
        if (competition['on'] and time.time() >= competition['time']['posix']):
            await end_competition()
            if not tracking:
                break
        if task.stopped():
            break

def worker():
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    new_loop.run_until_complete(log_loop(tx_filter, 2))

async def send_graphic(id : int) -> None:
    if buy_graphic['idx'] == 1:
        await application.bot.send_animation(chat_id=id, animation=buy_graphic["graphic"][0])
    elif buy_graphic['idx'] == 2:
        await application.bot.send_photo(chat_id=id, photo=buy_graphic["graphic"][1])
    elif buy_graphic['idx'] == 3:
        await application.bot.send_sticker(chat_id=id, sticker=buy_graphic["graphic"][2])

async def track(to_track: bool) -> None:
  """Starts/stops a thread running asyncio loop responsible for looking for new SHEBA transactions

  Args:
      tracking (bool): True if the thread is to be started, else False if it must be stopped.
  """
  global task
  if to_track:
      task = StoppableThread(target=worker, daemon=True)
      task.start()
  else:
      task.stop()
      task.join()


def keyboard(general : bool) -> InlineKeyboardMarkup:
    """ Generates either a general or competition inline keyboard to interact with the Bot's settings.

    Args:
        general (bool): True if a general keyboard is desired, otherwise False for a competition keyboard.

    Returns:
        InlineKeyboardMarkup: The markup for the specified inline keyboard.
    """
    settings = [
        [InlineKeyboardButton("❔Show Buys w/out Comp ✅" if tracking else "❔Show Buys w/out Comp 🚫", callback_data=str(ONE))],
        [InlineKeyboardButton("🎆 Buy GIF or Image ✅" if buy_graphic['idx'] else "🎆 Buy GIF or Image ⏫", callback_data=str(TWO))],
        [
            InlineKeyboardButton(buy_emoji +" Buy Emoji", callback_data=str(THREE)),
            InlineKeyboardButton("💲 Buy Step %d$" % buy_step, callback_data=str(FOUR)),
        ],
        [InlineKeyboardButton("Customize Buy Competition ⏩", callback_data=str(FIVE))],
    ] if general else [
        [
            InlineKeyboardButton("⏳ Length (%s minute)" % competition['values'][0], callback_data=str(ONE)),
            InlineKeyboardButton("⏫ Min Buy (%s BNB)" % competition['values'][1], callback_data=str(TWO)),
        ],
        [
            InlineKeyboardButton("🥇 Prize ({} BNB)".format(competition['values'][2] if competition['values'][2] != 0 else 'not set'), callback_data=str(FOUR)),
            InlineKeyboardButton("💎 Must Hold (%s hours)" % competition['values'][3], callback_data=str(THREE)),
        ],
        [
            InlineKeyboardButton("🥈 2nd Pr. ({})".format(competition['values'][4] + ' BNB' if competition['values'][4] != 0 else 'not set'), callback_data=str(FIVE)),
            InlineKeyboardButton("🥉 3rd Pr. ({})".format(competition['values'][5] + ' BNB' if competition['values'][5] != 0 else 'not set'), callback_data=str(SIX)),
        ],
        [InlineKeyboardButton("🕹 Current Mode: {}".format('Highest Buy' if competition['highest'] else 'Random'), callback_data=str(NINE))],
        [InlineKeyboardButton("🏆 Start Competition Now! 🏆", callback_data=str(SEVEN))],
        [InlineKeyboardButton("🔙 Go Back to Bot Settings", callback_data=str(EIGHT))]
    ]
    return InlineKeyboardMarkup(settings)

def get_dif() -> str:
    """ Generates a 'HH hours MM min SS sec' string from the amount of time left before a competition ends.

    Returns:
        str: A string contianing the number of hours minutes and seconds before an ongoing competition ends.
    """
    h, m, s = 0,0,0
    left = competition['time']['posix'] - time.time()
    s = ('0%d sec' % (left % 60)) if (left % 60) < 10 else ('%d sec' % (left % 60))
    m = '' if (((left / 60) % 60) == 0 and left // 3600 == 0) else ('0%d min ' % ((left / 60) % 60)) if ((left / 60) % 60) < 10 else ('%d min ' % ((left / 60) % 60))
    h = ('%d hours ' % left // 3600) if left // 3600 != 0 else ''

    return h + m + s

def prize_str() -> str:
    if competition['values'][4] != 0:
        if competition['values'][5] != 0:
            return '%s <b>BNB</b> (<i>2nd %s BNB, 3rd %s BNB</i>)' % (competition['values'][2], competition['values'][4], competition['values'][5])
        else:
            return '%s <b>BNB</b> (<i>2nd %s BNB</i>)' % (competition['values'][2], competition['values'][4])
    else:
        return '%s <b>BNB</b>' % competition['values'][2]

async def prompt(update: Update, text: str) -> None:
    """ Sends a given text prompting the user to perform a certain action as a preface for setting a certain parameter (through conversation).

    Args:
        update (Update): The update object from the user who called the function using this.
        text (str): The specified text.
    """
    query = update.callback_query
    await query.answer()
    id = update.callback_query.from_user.id
    await application.bot.send_message(chat_id = id, text=text, parse_mode=constants.ParseMode.HTML)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ Sends the Welcome message.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.
    """
    await update.message.reply_text(INITIAL_MESSAGE)

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sends an inline keyboard of general settings.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await update.message.reply_text(
      text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>",
      reply_markup=keyboard(True),
      parse_mode= constants.ParseMode.HTML)

    return START_PAGE

async def comp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sends an inline keyboard of competition settings.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    if competition['on']:
        results = None
        if len(competition['best']['buy']) > 0 and competition['highest']:
            buy = {k: v for k, v in sorted(competition['best']['buy'].items(), key=lambda item: item[1])}
            for i in reversed(range(3)):
                possible = len(buy.values()) > i
                if not possible:
                    continue
                else:
                    results = list(buy.items())[-(i+1):]
                    break
            medals = {0:'🥇', 1: '🥈', 2: '🥉'}
            winners = ''
            for i in range(len(results)):
                addr = results[i][0] if competition['highest'] else results[i]
                amnt = results[i][1] if competition['highest'] else ''
                winners += medals[i] + ' ' + addr[:6] +'...'+ addr[-4:]+ (('➖ %s BNB' % amnt) if competition['highest'] else '') +  '\n'
            msg = "🏁 <b>Buy competition ends in %s /comp\n🎖 Winning prize %s\n\n%s</b>" % (get_dif(), prize_str(), winners)  
        else:
            msg = "🏁 <b>Buy competition ends in %s /comp\n🎖 Winning prize %s\n\nThere are no buyers yet.</b>" % (get_dif(), prize_str())  
        if update.message:
              await update.message.reply_text(
              text=msg,
              parse_mode= constants.ParseMode.HTML)
        else:
            query = update.callback_query
            await query.answer()
            await query.from_user.send_message(
              text=msg,
              parse_mode= constants.ParseMode.HTML)
        return START_PAGE
    else:
        if update.message:
            await update.message.reply_text(
              text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>",
              reply_markup=keyboard(False),
              parse_mode= constants.ParseMode.HTML)
        else:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>", 
            reply_markup=keyboard(False),
            parse_mode=constants.ParseMode.HTML)
        return COMP_PAGE

    

async def toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Toggles the buy-tracking ability of the BestBuy bot

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    global tracking
    tracking = not tracking
    await refresh_settings(update, context)
    if not competition['on']:
        await track(tracking)

    return START_PAGE

async def invalid(update: Update, context: ContextTypes) -> int:
    """ Sends a canned reply for any invalid input. 

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await update.message.reply_text('❌ Invalid input.')

    return ConversationHandler.END

async def step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a new buy step.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, "➡️ Send new buy step (must be an integer)")

    return STEP

async def set_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sets a new buy step.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    global buy_step
    buy_step = int(update.message.text)

    await update.message.reply_text(
      text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>",
      reply_markup=keyboard(True),
      parse_mode= constants.ParseMode.HTML)
    return START_PAGE

async def emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a new buy emoji.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, "➡️ Send me a new emoji")

    return EMOJI
  
async def set_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sets a new buy emoji.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    global buy_emoji
    buy_emoji = update.message.text
    await update.message.reply_text(
      text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>",
      reply_markup=keyboard(True),
      parse_mode= constants.ParseMode.HTML)
    return START_PAGE

async def buy_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Prompts the user to set a new buy graphic.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, "➡️ Send Buy Gif/Sticker/Image\n\n Or use /reset to reset this")

    return GIF

async def set_gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sets a new gif, sticker or animation as the current buy graphic.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    gif = update.message.animation
    image = update.message.photo
    sticker = update.message.sticker
    if buy_graphic['idx']:
        buy_graphic['graphic'][buy_graphic['idx'] - 1] = None
    if gif:
        buy_graphic['graphic'][0] = gif
        buy_graphic['idx'] = 1
    elif image:
        buy_graphic["graphic"][1] = image
        buy_graphic['idx'] = 2
    elif sticker:
        buy_graphic['graphic'][2] = sticker
        buy_graphic['idx'] = 3
    await update.message.reply_text(
      text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>",
      reply_markup=keyboard(True),
      parse_mode= constants.ParseMode.HTML)
    
    return START_PAGE

async def reset_gif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Resets/removes the current buy graphic.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    buy_graphic['graphic'][buy_graphic['idx'] - 1] = None
    buy_graphic['idx'] = None

    return START_PAGE

async def begin_competition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Initiates a competition for the user using the currently parameter values.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    query = update.callback_query
    await query.answer()
    id = update.callback_query.from_user.id
    competition['id'] = id
    # Compute the time at which the competition starts/ends
    now = time.time()
    competition['time']['posix'] = now + (competition['values'][0] * 60)
    competition['time']['init'] = datetime.utcfromtimestamp(now)
    competition['time']['end'] = datetime.utcfromtimestamp(competition['time']['posix'])
    # Send the competition message and pin it
    await send_graphic(id)
    message = await application.bot.send_message(chat_id = id, text='<b>🎉 Buy Competition Started\n\n🕓 Start at %s\n⏳ End in %s\n⏫ Minimum Buy %s BNB\n\n💰 Winning Prize %s 🚀\n💎 Winner must hold at least %s hours</b>' % (competition['time']['init'].strftime("%H:%M:%S"), get_dif(), competition['values'][1], prize_str(), competition['values'][3]), parse_mode=constants.ParseMode.HTML)
    await message.pin()
    if tracking:
        await track(False)
    await track(True)
    competition['on'] = True

    return ConversationHandler.END

async def refresh_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Refreshes the last 'general settings' inline keyboard that was sent in a chat.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>", reply_markup=keyboard(True), parse_mode=constants.ParseMode.HTML)

    return START_PAGE

async def length(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a new competition duration.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me the competiton length in minutes (e.g 3)')
    competition["idx"] = 0

    return COMP

async def min_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a new minimum buy value for a competition.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me minimum buy (e.g 0.05)')
    competition["idx"] = 1

    return COMP

async def prize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a new minimum holding time period for a competition.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me winning prize (e.g 0.05)')
    competition["idx"] = 2

    return COMP

async def min_hold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a winner's prize value for a competition.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me a minimum holding time in hours (e.g 24)')
    competition["idx"] = 3

    return COMP

async def prize2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a second place prize value for a competition.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me second place prize (e.g 0.05)')
    competition["idx"] = 4

    return COMP

async def prize3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Prompts the user to set a third place prize value for a competition.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    await prompt(update, '➡️ Send me third place prize (e.g 0.05)')
    competition["idx"] = 5

    return COMP

async def set_comp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sets a new value for a competition parameter. 

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    competition['values'][competition['idx']] = float(update.message.text)
    await update.message.reply_text("⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>", reply_markup=keyboard(False), parse_mode=constants.ParseMode.HTML)

    return COMP_PAGE

async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ Sets a new value for the competition mode.

    Args:
        update (Update): The update object from the user who called this function.
        context (ContextTypes.DEFAULT_TYPE): The callback context of this function's handler.

    Returns:
        int: The expected state of the conversation handler after this function runs.
    """
    query = update.callback_query
    await query.answer()
    competition['highest'] = not competition['highest']
    await query.edit_message_text(text="⚙️ <b>Buy Bot Settings</b>\n\n<i>Biggest Buy Tech is an all in one buybot featuring automatic biggest buy contests. The Bot tracks cumulative buys to determine the winner!</i>", reply_markup=keyboard(False), parse_mode=constants.ParseMode.HTML)

    return COMP_PAGE

async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(competition['winners']['all'])
    update.message.reply_text(text='🏁 %d competitions have been completed so far' % total)
    for winner, amount in competition['winners']['all']:
        update.message.reply_text(text='<b>⏳ %s wins %s BNB</b>\n➡️ <a href=https://bscscan.com/address/%s>Wallet</a> | <a href=https://bscscan.com/token/0x08762be6631bef12efb750ff276e2e5095957afb?a=%s>Buy Txs</a>' % (winner, amount, winner, winner), parse_mode=constants.ParseMode.HTML)

async def cancel(update:Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END

def main() -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("settings", settings), 
                      CommandHandler("comp", comp),
                      CommandHandler("winners", results)],
        states={
            START_PAGE: [
                CallbackQueryHandler(toggle, pattern="^%d$" % ONE),
                CallbackQueryHandler(buy_gif, pattern="^%d$" % TWO),
                CallbackQueryHandler(emoji, pattern="^%d$" % THREE),
                CallbackQueryHandler(step, pattern="^%d$" % FOUR),
                CallbackQueryHandler(comp, pattern="^%d$" % FIVE)
            ],
            COMP_PAGE: [
                CallbackQueryHandler(length, pattern="^%d$" % ONE),
                CallbackQueryHandler(min_buy, pattern="^%d$" % TWO),
                CallbackQueryHandler(min_hold, pattern="^%d$" % THREE),
                CallbackQueryHandler(prize, pattern="^%d$" % FOUR),
                CallbackQueryHandler(prize2, pattern="^%d$" % FIVE),
                CallbackQueryHandler(prize3, pattern="^%d$" % SIX),
                CallbackQueryHandler(begin_competition, pattern="^%d$" % SEVEN),
                CallbackQueryHandler(refresh_settings, pattern="^%d$" % EIGHT),
                CallbackQueryHandler(mode, pattern="^%d$" % NINE)
            ],
            COMP: [
                MessageHandler(filters.Regex(r'^[\d]+[.]?[\d]*$'), set_comp),
                MessageHandler(~filters.Regex(r'^[\d]+[.]?[\d]*$'), invalid)
            ],
            GIF: [
                MessageHandler(filters.ANIMATION | filters.PHOTO | filters.Sticker.ALL, set_gif),
                MessageHandler(~(filters.ANIMATION | filters.PHOTO | filters.Sticker.ALL), invalid),
                CommandHandler("reset", reset_gif)
            ],
            EMOJI: [
                MessageHandler(filters.Regex(r'^[^\w\s,.]$'), set_emoji),
                MessageHandler(~filters.Regex(r'^[^\w\s,.]$'), invalid)
            ],
            STEP: [
              MessageHandler(filters.Regex(r'^[\d]+$'), set_step),
              MessageHandler(~filters.Regex(r'^[\d]+$'), invalid)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()