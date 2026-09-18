# Immediate ham feedback for messages moved out of Junk.
# Do not interpret deleting spam (moving it to Trash/Deleted folders) as ham.

require ["vnd.dovecot.pipe", "copy", "imapsieve", "environment", "variables"];

if environment :matches "imap.mailbox" "*" {
  set "mailbox" "${1}";
}

if string :matches "${mailbox}"
  ["Trash", "*.Trash", "Deleted Items", "*.Deleted Items",
   "Deleted Messages", "*.Deleted Messages", "Junk", "*.Junk", "Spam", "*.Spam"] {
  stop;
}

if environment :matches "imap.user" "*" {
  set "username" "${1}";
}

pipe :copy "ispconfig-rspamd-learn-ham" [ "${username}" ];
