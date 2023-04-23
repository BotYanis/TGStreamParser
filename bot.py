import logging

import aiofiles
from aiogram import Bot, Dispatcher, executor
from aiogram.dispatcher.filters import CommandStart, Text
from aiogram.types import Message, ParseMode, InputFile, ContentTypes, InlineKeyboardButton, InlineKeyboardMarkup
from environs import Env
from pyrogram import Client
from pyrogram.errors import Unauthorized
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.phone import GetGroupCall
from pyrogram.raw.types import PeerUser

env = Env()
env.read_env()


ADMINS_ID = [] # Your TG id


async def start_bot(message: Message):
    await message.answer(
        '<b>🤚 Привет! Введите username канала (например, @mychannel)</b>\n'
    )


async def parse_stream(message: Message):
    msg = await message.answer(
        '<b>⏳ Запускаю парсер...</b>'
    )
    client = Client(
        'session',
        env.int('API_ID'),
        env.str('API_HASH')
    )
    try:
        async with client:
            channel_call = (
                await client.invoke(
                    GetFullChannel(
                        channel=await client.resolve_peer(message.text.strip('@'))
                    )
                )
            ).full_chat.call
            if not channel_call:
                return await msg.edit_text(
                    '<b>❌ Трансляция не запущена!</b>'
                )
            participants = [
                member.peer.user_id
                for member in (
                    await client.invoke(
                        GetGroupCall(
                            call=channel_call,
                            limit=12_000
                        )
                    )
                ).participants if isinstance(member.peer, PeerUser)
            ]
            members_usernames = await client.get_users(participants)
            if not participants:
                return await msg.edit_text(
                    '<b>❌ Отсутвуют пользователи на трансляции</b>'
                )

        parsed_users = 0
        async with aiofiles.open('participants.txt', 'w') as file:
            for user in members_usernames:
                if not user.username:
                    if user.phone_number:
                        await file.write(f'{user.phone_number}\n')
                        parsed_users += 1
                else:
                    await file.write(f'{user.username}\n')
                    parsed_users += 1

        if parsed_users == 0:
            return await msg.edit_text(
                f'❌ Спаршено: <b>0/{len(participants)}</b>'
            )
        await msg.delete()
        await message.answer_document(
            document=InputFile('participants.txt'),
            caption=f'👤 Спаршено: <b>{parsed_users}/{len(participants)}</b>\n\n'
        )
    except Unauthorized:
        return await msg.edit_text(
            f'<b>⚠️ Сессия невалидная!</b>'
        )
    except Exception as ex:
        await message.answer(
            f'<b>⚠️ Произошла ошибка:</b>\n<code>{ex}</code>'
        )


async def replace_session(message: Message):
    if not message.document.file_name.endswith('.session'):
        return await message.reply(
            '<b>❌ Файл сессии должен заканчиваться на .session</b>'
        )
    await message.document.download(destination_file='session.session')
    msg = await message.answer(
        '<b>⏳ Проверка сессии...</b>'
    )
    client = Client(
        'session',
        env.int('API_ID'),
        env.str('API_HASH')
    )
    try:
        async with client:
            if await client.get_me():
                return await msg.edit_text(
                    '<b>✅ Заменил сессию!</b>'
                )
    except Exception:
        return await msg.edit_text(
            f'<b>⚠️ Сессия невалидная!</b>'
        )


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(
        start_bot,
        CommandStart()
    )
    dp.register_message_handler(
        parse_stream,
        Text(startswith='@')
    )
    dp.register_message_handler(
        replace_session,
        content_types=ContentTypes.DOCUMENT,
        user_id=ADMINS_ID
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bot = Bot(env.str('BOT_TOKEN'), parse_mode=ParseMode.HTML)
    dp = Dispatcher(bot)
    register_handlers(dp)
    executor.start_polling(dp)
