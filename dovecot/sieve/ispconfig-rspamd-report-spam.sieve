# Immediate spam feedback for messages moved into Junk.
# Independently implemented from current Dovecot IMAPSieve documentation;
# train-spam-scanner (BSD-2-Clause) is credited as prior art.

require ["vnd.dovecot.pipe", "copy", "imapsieve", "environment", "variables"];

if environment :matches "imap.user" "*" {
  set "username" "${1}";
}

pipe :copy "ispconfig-rspamd-learn-spam" [ "${username}" ];
