#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.

"""
Basic example for a bot that uses inline keyboards.
"""
import json
import logging
import os
from pathlib import Path

from firefly import Firefly
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardRemove, Update, ReplyKeyboardMarkup)
from telegram.ext import (CallbackQueryHandler, CommandHandler,
                          ConversationHandler, Filters, MessageHandler,
                          PicklePersistence, Updater, CallbackContext)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

FIREFLY_URL, FIREFLY_TOKEN, DEFAULT_WITHDRAW_ACCOUNT = range(3)
DESCRIPTION, SOURCE, DEST, AMOUNT = range(4)

def start(update, context):
    update.message.reply_text("Please enter your Firefly III URL")
    return FIREFLY_URL


def get_firefly_token(update, context):
    firefly_url = update.message.text
    context.user_data["firefly_url"] = firefly_url
    update.message.reply_text("""
    Please enter your Firefly III User Token
    \nYou can generate it from the OAuth section here - {}/profile""".format(firefly_url))
    return DEFAULT_WITHDRAW_ACCOUNT

def get_default_account(update, context):
    token = update.message.text
    firefly = Firefly(hostname=context.user_data.get(
        "firefly_url"), auth_token=token)
    accounts = firefly.get_accounts(account_type="asset").get("data")

    accounts_keyboard = []
    for account in accounts:
        account_name = account.get("attributes").get("name")
        accounts_keyboard.append([InlineKeyboardButton(
            account_name, callback_data=account.get("id"))])

    reply_markup = InlineKeyboardMarkup(accounts_keyboard)

    context.user_data["firefly_token"] = update.message.text
    update.message.reply_text(
        "Please choose the default Source account:", reply_markup=reply_markup)
    return DEFAULT_WITHDRAW_ACCOUNT


def store_default_account(update, context):
    query = update.callback_query
    default_account_id = query.data
    context.user_data["firefly_default_account"] = default_account_id
    query.edit_message_text("Setup Complete. Happy Spending!(?)")
    return ConversationHandler.END


def spend(update, context):

    def safe_list_get(l, idx):
        try:
            return l[idx]
        except IndexError:
            return None

    message = update.message.text
    if "," not in message:
        message_data = message.split(" ")
    else:
        message_data = message.split(",")

    message_data = [value.strip() for value in message_data]

    if len(message_data) < 2:
        update.message.reply_text(
            "Just type in an expense with a description. Like this - '5 Starbucks`")
        return

    amount = safe_list_get(message_data, 0)
    description = safe_list_get(message_data, 1)
    category = safe_list_get(message_data, 2)
    budget = safe_list_get(message_data, 3)
    source_account = safe_list_get(message_data, 4)
    destination_account = safe_list_get(message_data, 5)

    firefly = get_firefly(context)
    if not source_account:
        source_account = context.user_data["firefly_default_account"]

    response = firefly.create_transaction(amount, description,
                                          source_account, destination_account, category, budget)
    if response.status_code == 422:
        update.message.reply_text(response.get("message"))
    elif response.status_code == 200:
        try:
            id = response.json().get("data").get("id")
            firefly_url = context.user_data.get("firefly_url")
            update.message.reply_markdown(
                "[Expense logged successfully]({0}/transactions/show/{1})".format(
                    firefly_url, id
                ))
        except:
            update.message.reply_text("Please check input values")
    else:
        update.message.reply_text("Something went wrong, check logs")


def about(update, context):
    firefly = get_firefly(context)
    about = firefly.get_about_user()
    update.message.reply_text("```{}```".format(about))


def get_firefly(context):
    return Firefly(hostname=context.user_data.get("firefly_url"), auth_token=context.user_data.get("firefly_token"))


def help(update, context):
    if not context.user_data.get("firefly_default_account"):
        update.message.reply_text("Type /start to initiate the setup process.")
    else:
        update.message.reply_markdown("""
All you need to do is send a message to the bot with the following format -
`Amount, Description, Category, Budget, Source account, Destination account`

Only the first two values are needed. The rest are optional. The description value is used for destination account as well.

A simple one -
        `5, Starbucks`

One with all the fields being used -
        `5, Mocha with an extra shot for Steve, Coffee, Food Budget, UCO Bank, Starbucks`

You can skip specfic fields by leaving them empty (except the first two) -
        `5, Starbucks, , Food Budget, UCO Bank`
""")

def get_defaultAsset_keyboard(firefly):
    accounts = firefly.get_accounts(account_type="asset").get("data")
    accounts_keyboard = []
    for i, account in enumerate(accounts):
        if i % 3 == 0:
            accounts_keyboard.append([])
        account_name = account.get("attributes").get("name")
        account_id = account.get("id")
        comp = dict(name=account_name, id=account_id)
        comstr = json.dumps(comp)
        if account.get("attributes").get("account_role") == "defaultAsset":
            accounts_keyboard[-1].append(InlineKeyboardButton(
                account_name, callback_data=comstr))

    return InlineKeyboardMarkup(accounts_keyboard)

def get_balance(update, context):
    firefly = get_firefly(context)

    reply_markup = get_defaultAsset_keyboard(firefly)
    update.message.reply_text(
        "What balance do you want to know?", reply_markup=reply_markup)
    return 0

def show_balance(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    asset_account = json.loads(query.data)
    firefly = get_firefly(context)
    account = firefly.get_account(asset_account['id']).get("data")
    account_name = account.get("attributes").get("name")
    balance = account.get("attributes").get("current_balance")
    curr = account.get("attributes").get("currency_code")
    query.edit_message_text(text=f"The balance of {account_name} is {curr} {balance}")
    return ConversationHandler.END


def start_expense(update, context):
    firefly = get_firefly(context)
    reply_markup = get_defaultAsset_keyboard(firefly)

    update.message.reply_text(
        "Enter a description")
    return DESCRIPTION

def get_expense_account(update, context):
    firefly = get_firefly(context)

    # store the descriiption
    context.user_data["description"] = update.message.text
    # check if rule exists
    rules = firefly.get_rules().get("data")

    matched_rules = []

    for rule in rules:
        rule_title = rule.get("attributes").get("title")
        rule_triggers = rule.get("attributes").get("triggers")
        rule_actions = [action.get("type") for action in rule.get("attributes").get("actions")]
        for trigger in rule_triggers:
            if (trigger.get("type") == "description_contains"
                and  trigger.get("value").lower() in update.message.text.lower()
                and 'set_source_account' in rule_actions
                and 'set_destination_account' in rule_actions):
                matched_rules.append(rule)

    if len(matched_rules) == 1:
        rule = matched_rules[0]
        triggers = rule.get("attributes").get("triggers")
        title = rule.get("attributes").get("title")
        further_cond = []
        for trigger in triggers:
            if trigger.get("type") != "description_contains":
                further_cond.append(f"{trigger.get('type')}: {trigger.get('value')}")

        list = "\n".join(further_cond)

        context.user_data["asset_account"] = dict(id="1", name="Credit Suisse")
        context.user_data["expense_account"] = "dummy"

        update.message.reply_markdown(f"*{title}*\nPlease enter amount:")
        return AMOUNT
    else:
        reply_markup = get_defaultAsset_keyboard(firefly)
        update.message.reply_text(
            "Chose from which account to spend", reply_markup=reply_markup)
        return SOURCE


def get_withdraw_account(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    context.user_data["asset_account"] = json.loads(query.data)

    firefly = get_firefly(context)
    accounts = firefly.get_accounts(account_type="expense").get("data")
    accounts_keyboard = []
    accounts = [a for a in accounts if a.get("attributes").get("active")]
    for i, account in enumerate(accounts):
        if i % 3 == 0:
            accounts_keyboard.append([])
        account_name = account.get("attributes").get("name")
        accounts_keyboard[-1].append(account_name)

    markup = ReplyKeyboardMarkup(accounts_keyboard, one_time_keyboard=True)

    # update.send_message("Chose an expense account:", reply_markup=markup)
    query.edit_message_text(query.data)
    query.message.reply_text("Chose an expense account", reply_markup=markup)
    return DEST

def get_amount(update, context):
    context.user_data["expense_account"] = update.message.text

    update.message.reply_text("Now, please, enter an amount:")
    #return ConversationHandler.END
    return AMOUNT

def summarize(update, context):
    asset_account = context.user_data.get("asset_account")
    expense_account = context.user_data.get("expense_account")
    description = context.user_data.get("description")
    update.message.reply_text(f"Withdraw from {asset_account['name']} to {expense_account}, amount {update.message.text}, description: {description}")

    firefly = get_firefly(context)
    response = firefly.create_transaction(update.message.text, description,
                                          asset_account['id'], expense_account)
    if response.status_code == 422:
        update.message.reply_text(response.get("message"))
    elif response.status_code == 200:
        try:
            id = response.json().get("data").get("id")
            firefly_url = context.user_data.get("firefly_url")
            update.message.reply_markdown(
                "[Expense logged successfully]({0}/transactions/show/{1})".format(
                    firefly_url, id
                ))
        except:
            update.message.reply_text("Please check input values")
    else:
        update.message.reply_text("Something went wrong, check logs")

    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Cancelled")
    return ConversationHandler.END


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning("Update '%s' caused error '%s'", update, context.error)


def main():
    data_dir = os.getenv("CONFIG_PATH", "")
    if not data_dir:
        data_dir = Path.joinpath(Path.home(), ".config", "firefly-bot")
        data_dir.mkdir(parents=True, exist_ok=True)
    else:
        data_dir = Path(data_dir)
    bot_persistence = PicklePersistence(filename=str(data_dir/"bot-data"))
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    updater = Updater(bot_token,
                      persistence=bot_persistence, use_context=True)

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIREFLY_URL: [MessageHandler(Filters.text, get_firefly_token)],
            DEFAULT_WITHDRAW_ACCOUNT: [MessageHandler(Filters.text, get_default_account),
                                       CallbackQueryHandler(store_default_account, pattern="^[0-9]*$")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    expense = ConversationHandler(
        entry_points=[CommandHandler("expense", start_expense)],
        states={
            DESCRIPTION: [MessageHandler(Filters.text, get_expense_account)],
            SOURCE: [CallbackQueryHandler(get_withdraw_account)],
            DEST: [MessageHandler(Filters.text, get_amount)],
            AMOUNT: [MessageHandler(Filters.text, summarize)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    balance = ConversationHandler(
        entry_points=[CommandHandler("balance", get_balance)],
        states={
            0: [CallbackQueryHandler(show_balance)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    updater.dispatcher.add_handler(expense)
    updater.dispatcher.add_handler(balance)
    updater.dispatcher.add_handler(CommandHandler("help", help))
    updater.dispatcher.add_handler(CommandHandler("about", about))
    #updater.dispatcher.add_handler(MessageHandler(
    #    filters=Filters.regex("^[0-9]+"), callback=spend))
    updater.dispatcher.add_error_handler(error)
    updater.dispatcher.add_handler(conversation_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == "__main__":
    main()
