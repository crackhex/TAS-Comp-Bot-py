import discord
import sqlite3
import aiofiles
import os
from utils import is_task_currently_running, download_attachments, get_lap_time, readable_to_float, float_to_readable

def get_submission_channel(comp):
    connection = sqlite3.connect("database/settings.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM submission_channel WHERE comp = ?", (comp,))
    result = cursor.fetchone()

    if result is not None:  # Check if result is not None before accessing index
        channel_id = result[1]
        return channel_id
    else:
        # Handle case where no rows are found in the database
        print(f"No submission channel found for competition '{comp}'.")
        return None  # or raise an exception, depending on your application's logic


def first_time_submission(id):
    """Check if a certain user id has submitted to this competition already"""
    connection = sqlite3.connect("database/tasks.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM submissions WHERE id = ?", (id,))
    result = cursor.fetchone()
    return not result

def new_competitor(id):
    """Checks if a competitor has EVER submitted (present and past tasks)."""
    connection = sqlite3.connect("database/users.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM userbase WHERE id = ?", (id,))
    result = cursor.fetchone()
    connection.close()
    return not result

def get_display_name(id):
    """Returns the display name of a certain user ID."""
    connection = sqlite3.connect("database/users.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM userbase WHERE id = ?", (id,))
    result = cursor.fetchone()
    connection.close()
    return result[2]

def count_submissions():
    """Counts the number of submissions in the current task."""
    connection = sqlite3.connect("database/tasks.db")
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM submissions")
    result = cursor.fetchall()
    connection.close()

    return len(result)


# old parameters: message, file, num, year
async def handle_submissions(message, self):

    author = message.author
    author_name = message.author.name
    author_id = message.author.id
    author_dn = message.author.display_name

    # Checking if submitter has ever participated before
    if new_competitor(author_id):
        # adding him to the user database.
        connection = sqlite3.connect("database/users.db")
        cursor = connection.cursor()
        cursor.execute("INSERT INTO userbase (user, id, display_name) VALUES (?, ?, ?)",
                       (author_name, author_id, author_dn))
        connection.commit()
        connection.close()

    ##################################################
    # Adding submission to submission list channel
    ##################################################
    submission_channel = get_submission_channel("mkw")
    channel = self.bot.get_channel(submission_channel)

    if not channel:
        print("Could not find the channel.")
        return

    async for msg in channel.history(limit=1):
        last_message = msg
        break
    else:
        last_message = None

    if last_message:
        # Try to find an editable message by the bot
        if last_message.author == self.bot.user:

            # Add a new line only if it's a new user ID submitting
            if first_time_submission(author_id):
                new_content = f"{last_message.content}\n{count_submissions()}. {get_display_name(author_id)} ||{author.mention}||"
                await last_message.edit(content=new_content)
        else:
            # If the last message is not sent by the bot, send a new one
            await channel.send(f"**__Current Submissions:__**\n1. {get_display_name(author_id)} ||{author.mention}||")
    else:
        # There are no submissions (brand-new task); send a message on the first submission -> this is for blank channels
        await channel.send(f"**__Current Submissions:__**\n1. {get_display_name(author_id)} ||{author.mention}||")




async def handle_dms(message, self):
    
    author = message.author
    author_name = message.author.name
    author_id = message.author.id
    author_dn = message.author.display_name

    if isinstance(message.channel, discord.DMChannel) and author != self.bot.user:

        # this logs messages to a channel -> my private server for testing purposes
        channel = self.bot.get_channel(1243652270537707722)
        attachments = message.attachments
        if len(attachments) > 0:
            filename = attachments[0].filename
            url = attachments[0].url
        if channel:
            await channel.send("Message from " + str(author_dn) + ": " + message.content + " "
                               .join([attachment.url for attachment in message.attachments if message.attachments]))

        #########################
        # Recognizing submission
        #########################
        
        connection = sqlite3.connect("database/tasks.db")
        cursor = connection.cursor()
        
        current_task = is_task_currently_running()

        #################################
        # recognition of rkg submission
        #################################

        if attachments and filename.endswith('.rkg'):

            if current_task:
                
                # Tell the user the submission has been received
                print(f"File received!\nBy: {author}\nMessage sent: {message.content}")
                await message.channel.send(
                    "`.rkg` file detected!\nThe file was successfully saved. Type `/info` for more information about the file.")

                # handle submission
                await handle_submissions(message, self)



                # retrieving lap time, to estimate submission time

                rkg_data = await attachments[0].read()

                try:
                    rkg = bytearray(rkg_data)
                    if rkg[:4] == b'RKGD':
                        lap_times = get_lap_time(rkg)

                    # float time to upload to db
                    time = readable_to_float(lap_times[0]) # For most (but not all) mkw single-track tasks, the first lap time is usually the time of the submission, given the task is on lap 1 and not backwards.

                except UnboundLocalError:
                    # This exception catches blank rkg files
                    time = 0
                    await message.channel.send("Nice blank rkg there")



                # Add first-time submission
                if first_time_submission(author_id):
                    # Assuming the table `submissions` has columns: task, name, id, url, time, dq, dq_reason
                    cursor.execute(
                        "INSERT INTO submissions (task, name, id, url, time, dq, dq_reason) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                        (current_task[0], author_name, author_id, url, time, 0, '')
                    )
                    connection.commit()
                    connection.close()


                # If not first submission: replace old submission
                else:
                    cursor.execute("UPDATE submissions SET url=?, time=? WHERE id=?", (url, time, author_id))
                    connection.commit()
                    connection.close()

            # No ongoing task
            else:
                await message.channel.send("There is no active task.")

        #################################
        # recognition of rksys submission
        #################################


        elif attachments and filename.endswith('.dat'):

            if current_task:

                # handle submission
                await handle_submissions(message, self)


                # Add first-time submission
                if first_time_submission(author_id):
                    cursor.execute(
                        f"INSERT INTO submissions VALUES (task, name, id, url, time, dq, dq_reason) VALUES (?, ?, ?, ?, ?, ?)", (current_task[0], author_name, author_id, url, 0, 0, ''))
                    connection.commit()
                    connection.close()

                # If not first submission: replace old submission
                else:
                    cursor.execute("UPDATE submissions SET url=? WHERE id=?", (url, author_id))
                    connection.commit()
                    connection.close()

                # Tell the user the submission has been received
                print(f"File received!\nBy: {author}\nMessage sent: {message.content}")
                await message.channel.send(
                    "`rksys.dat` detected!\nThe file was successfully saved. Type `/info` for more information about the file.")


            else:
                await message.channel.send("There is no active task.")

            # TODO make info command be an actual info command