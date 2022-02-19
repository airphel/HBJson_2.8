import os

CMD_REBOOT         	= 800		# REBOOT	
CMD_SHUTDOWN       	= 801       # SHUTDOWN
CMD_RESTART_MONITOR	= 802       # RESTART HBJSON
CMD_RESTART_HBNET	= 803       # RESTART HBNET	

def rts_update_extra(destination):
  if destination == CMD_REBOOT:
      os.system('reboot')
  elif destination == CMD_SHUTDOWN:
      os.system('shutdown')
  elif destination == CMD_RESTART_MONITOR:
      os.system('sudo systemctl restart hbjson.service')
  elif destination == CMD_RESTART_HBNET:
      os.system('sudo systemctl restart hbnet.service')

