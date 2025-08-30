import os
import re
import logging
import asyncio
from typing import Dict, List, Optional
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, ChannelPrivate, FloodWait

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = int(os.environ.get("API_ID", 12345))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
SESSION_STRING = os.environ.get("SESSION_STRING", "your_session_string_here")

# Add your channel IDs here (including the ones you mentioned)
CONNECTED_CHANNELS = [
    -10074849,      # Replace with actual channel ID
    -1008484894,    # Replace with actual channel ID
    # Add more channels as needed
]

# Store user sessions
user_sessions = {}

# Initialize clients
bot = Client("auto_post_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_client = Client("user_account", session_string=SESSION_STRING, api_id=API_ID, api_hash=API_HASH)

async def is_user_member(user_id: int, channel_id: int) -> bool:
    """Check if user is member of the channel"""
    try:
        member = await user_client.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except (UserNotParticipant, ChannelPrivate, ValueError):
        return False

async def is_bot_admin(channel_id: int) -> bool:
    """Check if bot has admin permissions in channel"""
    try:
        member = await bot.get_chat_member(channel_id, "me")
        return member.can_change_info if member else False
    except (ChatAdminRequired, ChannelPrivate, ValueError):
        return False

async def search_in_channel(channel_id: int, query: str, message: Message):
    """Search for posts in a specific channel"""
    try:
        found_messages = []
        async for msg in user_client.search_messages(channel_id, query=query, limit=20):
            if msg.text or msg.caption:
                content = msg.text or msg.caption
                # Look for movie patterns
                if re.search(r'\b(1080p|720p|480p|HD|BluRay|DVDScr|WebDL|HDRip|BRRip|TS|TC|CAM)\b', content, re.IGNORECASE):
                    # Extract title and quality info
                    title_match = re.search(r'^(.*?)(?=\d{4}|\[|\(|HD|1080p|720p|480p)', content, re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else "Unknown Title"
                    
                    year_match = re.search(r'\((\d{4})\)', content)
                    year = year_match.group(1) if year_match else ""
                    
                    quality_match = re.search(r'\b(1080p|720p|480p|HD|BluRay|DVDScr|WebDL|HDRip|BRRip|TS|TC|CAM)\b', content, re.IGNORECASE)
                    quality = quality_match.group(1) if quality_match else ""
                    
                    language_match = re.search(r'\[(.*?)\]', content)
                    languages = language_match.group(1) if language_match else ""
                    
                    # Create message link
                    message_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/{msg.id}"
                    
                    result_text = f"🍿 {title} {f'({year})' if year else ''} {f'[{languages}]' if languages else ''} {quality}\n🔗 📥 Download Here ({message_link})"
                    found_messages.append(result_text)
        
        return found_messages
    except Exception as e:
        logger.error(f"Error searching in channel {channel_id}: {e}")
        return []

@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    welcome_text = """
🎬 Welcome to Movie Search Bot! 🎬

I can search for movies across multiple channels.

Simply send me the movie name you're looking for, and I'll find it for you!

Example: `Avengers Endgame`
    """
    await message.reply_text(welcome_text)

@bot.on_message(filters.text & filters.private & ~filters.command("start"))
async def search_movies(client: Client, message: Message):
    """Handle movie search requests"""
    user_id = message.from_user.id
    query = message.text.strip()
    
    # Send initial searching message
    search_msg = await message.reply_text(f"🔍 Searching for '{query}' across channels...")
    
    # Check if user is member of all connected channels
    for channel_id in CONNECTED_CHANNELS:
        if not await is_user_member(user_id, channel_id):
            await search_msg.edit_text(f"❌ You need to join all connected channels to use this bot.\n\nPlease join channel {channel_id} and try again.")
            return
    
    # Check if bot is admin in all channels
    for channel_id in CONNECTED_CHANNELS:
        if not await is_bot_admin(channel_id):
            await search_msg.edit_text(f"❌ Bot doesn't have required permissions in channel {channel_id}.")
            return
    
    # Search in all channels
    all_results = []
    for channel_id in CONNECTED_CHANNELS:
        try:
            # Update search status
            await search_msg.edit_text(f"🔍 Searching in channel {channel_id} for '{query}'...")
            
            # Search in this channel
            results = await search_in_channel(channel_id, query, message)
            all_results.extend(results)
            
            # Add small delay to avoid flooding
            await asyncio.sleep(1)
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error(f"Error processing channel {channel_id}: {e}")
    
    # Prepare and send results
    if all_results:
        # Limit to 10 results to avoid message too long error
        limited_results = all_results[:10]
        
        results_text = "🎬 Search Results 🎬\n\n" + "\n\n".join(limited_results)
        
        # Add more results notice if we limited them
        if len(all_results) > 10:
            results_text += f"\n\n... and {len(all_results) - 10} more results found!"
        
        await search_msg.edit_text(results_text)
    else:
        await search_msg.edit_text(f"❌ No results found for '{query}' in any connected channels.")

async def main():
    """Start the bot and user client"""
    await bot.start()
    await user_client.start()
    
    # Log bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started as @{bot_info.username}")
    
    # Log user info
    user_info = await user_client.get_me()
    logger.info(f"User client started as @{user_info.username}")
    
    # Check channel permissions
    for channel_id in CONNECTED_CHANNELS:
        try:
            # Check bot admin status
            bot_member = await bot.get_chat_member(channel_id, "me")
            logger.info(f"Bot admin status in {channel_id}: {bot_member.can_change_info}")
            
            # Check user client access
            await user_client.get_chat(channel_id)
            logger.info(f"User client has access to {channel_id}")
            
        except Exception as e:
            logger.error(f"Error checking channel {channel_id}: {e}")
    
    await idle()
    
    await bot.stop()
    await user_client.stop()

if __name__ == "__main__":
    # Create event loop and run
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
