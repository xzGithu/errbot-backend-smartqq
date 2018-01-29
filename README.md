# errbot-backend-qq


This can only reply the simple text,  when your message should reply by a large message,the message can't be send to you QQ IM

like:
!hello you send, it cant reply with a hello to you.

but when you send !status. etc.  the replied msg cant be send back to IM


Usage:

Download:
Download this package into your errbot backend dir, and unpack it.

git clone git@github.com:xzGithu/errbot-backend-smartqq.git

Config.py:

BOT_EXTRA_BACKEND_DIR = r'/path/to/backendse/qq'

BACKEND = 'qq'

BOT_IDENTITY={
    "grouptoken":"group name",#just use for login.
}

BOT_ADMINS = ('@nickname')# group member's nickname
