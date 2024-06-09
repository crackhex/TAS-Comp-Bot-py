import hashlib
import os
import uuid
from urllib.parse import urlparse
import requests
from discord.ext import commands
import json
import sqlite3
from sqlalchemy import select, insert, update
from api.db_classes import Money, Submissions, SubmissionChannel, Tasks, HostRole, Userbase, session
from dotenv import load_dotenv

load_dotenv()
DEFAULT = os.getenv('DEFAULT')  # Choices: mkw, sm64
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR')
DB_DIR = os.getenv('DB_DIR')


def get_balance(user_id):
    money = session.scalars(select(Money).where(Money.user_id == user_id)).first()
    if money is None:
        balance = 100
        stmt = (insert(Money).values(user_id=user_id, coins=balance))
        session.execute(stmt)
        session.commit()
    else:
        balance = money.coins
    return balance


def update_balance(user_id, new_balance):
    stmt = (update(Money).values(user_id=user_id, coins=new_balance))
    session.execute(stmt)
    session.commit()


def add_balance(user_id, amount):
    current_balance = get_balance(user_id)
    new_balance = current_balance + amount
    update_balance(user_id, new_balance)


def deduct_balance(username, amount):
    current_balance = get_balance(username)
    new_balance = max(current_balance - amount, 0)  # Ensure balance doesn't go negative
    update_balance(username, new_balance)


def get_host_role():
    default = DEFAULT
    """Retrieves the host role. By default, on the server, the default host role is 'Host'."""
    host_role = session.scalars(select(HostRole.role_id).where(HostRole.comp == default)).first()

    if host_role:
        print(host_role)
        return host_role
    else:
        return "Host"  # default host role name.


def has_host_role():
    async def predicate(ctx):
        role = get_host_role()
        # Check if the role is a name
        has_role = ctx.author.get_role(role) is not None
        return has_role

    return commands.check(predicate)


async def download_from_url(url) -> str:
    try:
        url_parsed = urlparse(url)
        filename, file_extension = os.path.splitext(os.path.basename(url_parsed.path))
        file_path = os.path.join(DOWNLOAD_DIR, f"{filename}{file_extension}")

        file = requests.get(url)
        if not file.ok:
            return None
        open(file_path, 'wb').write(file.content)

        return file_path

    except:

        return None


async def check_json_guild(file, guild_id):  # TODO: Normalise file handling, rename function
    with open(file, "r") as f:

        data = json.loads(f.read())
        for guild in data:
            if guild == guild_id:
                return True

    return False


def readable_to_float(time_str):
    """Convert a time string 'M:SS.mmm' to seconds (float)."""
    try:
        minutes, seconds = time_str.split(':')
        minutes = int(minutes)
        seconds = float(seconds)
        total_seconds = minutes * 60 + seconds
        return total_seconds
    except ValueError:
        print("Invalid time format. Expected 'MM:SS.mmm'.")


def float_to_readable(seconds):
    """Convert seconds (float) to a time string 'M:SS.mmm'."""
    if seconds < 0:
        print("Seconds cannot be negative.")
        return

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    time_str = f"{minutes}:{remaining_seconds:06.3f}"
    return time_str


def is_task_currently_running():
    """Check if a task is currently running"""
    connection = sqlite3.connect("./database/tasks.db")
    cursor = connection.cursor()

    # Is a task running?
    cursor.execute("SELECT * FROM tasks WHERE is_active = 1")
    currently_running = cursor.fetchone()
    connection.close()
    return currently_running


def calculate_winnings(num_emojis, slot_number, constant=3):
    probability = 1 / (num_emojis ** (slot_number - 1))
    winnings = constant * slot_number * (1 / probability)
    return int(winnings)


def get_file_types(attachments):
    file_list = []
    for file in attachments:
        file_list.append(file.filename.rpartition(".")[-1])
    file_tuples = enumerate(file_list)
    # Check for uniqueness by assigning index to dictionary
    # Iterates over dictionary to find if an index has been assigned
    file_dict = {}
    for index, filetype in file_tuples:
        if filetype not in file_dict:
            file_dict[filetype] = index
    return file_dict


def hash_file(filename: str):
    """Hashes a file's contents

    Args:
        filename (str): Path to a file

    Returns:
        _Hash: The file contents' hash
    """
    with open(filename, 'rb', buffering=0) as f:
        return hashlib.file_digest(f, 'sha256')
