import smtplib

class NotifyError(Exception):
    def __init__(self, message):
        self.message = message

class SMTP(object):
    def __init__(self, config, dry_run):
        self.dry_run = dry_run
        self.hostname = config.smtp.hostname
        self.username = config.smtp.username
        self.passwd = config.smtp.passwd
        self.address = config.smtp.address
        self.contact_info = config.smtp.contact_info
        self.message_template = '\r\n'.join(['From: '+self.address,
                                  'To: {}',
                                  'Subject: ['+config.name+'] Notifications',
                                  '',
                                  'Greetings Human {},',
                                  '',
                                  '{}'
                                  '',
                                  'Beep boop,',
                                  config.name + ' Email Bot'])
        self.notifications = {}
        self.connected = False

    def submit(self, recipient, message):
        if recipient not in self.notifications:
            self.notifications[recipient] = []
        self.notifications[recipient].append(message)

    def connect(self):
        self.server = smtplib.SMTP(self.hostname)
        self.server.ehlo()
        self.server.starttls()
        self.server.login(self.username, self.passwd)
        self.connected = True

    #TODO implement saving messages to disk with timestamp if send fails
    def notify(self, recipient, message):
        if not self.connected:
            raise NotifyError('Not connected to SMTP server; cannot send notifications')
        self.server.sendmail(self.address, 
				self.contact_info[recipient]['address'], 
				self.message_template.format(self.contact_info[recipient]['address'], self.contact_info[recipient]['name'], message)
                            )

    def notify_all(self):
        if not self.connected:
            raise NotifyError('Not connected to SMTP server; cannot send notifications')
        for recip in self.notifications:
            if len(self.notifications[recip]) > 0:
                self.notify(recip, '\r\n\r\n-------------------\r\n\r\n'.join(self.notifications[recip]))
            self.notifications[recip] = []

    def close(self):
        if self.connected:       
            self.server.quit()
            self.connected = False



