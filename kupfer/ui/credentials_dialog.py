import gtk

from kupfer import version, config, kupferstring

class CredentialsDialogController():
	def __init__(self, username, password):
		"""Load ui from data file"""
		builder = gtk.Builder()
		builder.set_translation_domain(version.PACKAGE_NAME)
		ui_file = config.get_data_file("credentials_dialog.ui")
		builder.add_from_file(ui_file)
		builder.connect_signals(self)

		self.window = builder.get_object("credentials_dialog")
		self.entry_user = builder.get_object('entry_username')
		self.entry_pass = builder.get_object('entry_password')

		self.entry_user.set_text(username or '')
		self.entry_pass.set_text(password or '')

	def on_button_ok_clicked(self, widget):
		self.window.response(gtk.RESPONSE_ACCEPT)
		self.window.hide()

	def on_button_cancel_clicked(self, widget):
		self.window.response(gtk.RESPONSE_CANCEL)
		self.window.hide()

	def show(self):
		return self.window.run()

	@property
	def username(self):
		return kupferstring.tounicode(self.entry_user.get_text())

	@property
	def password(self):
		return kupferstring.tounicode(self.entry_pass.get_text())


def ask_user_credentials(user=None, password=None):
	''' Ask user for username and password.
	
	@user, @password - initial values
	@return:
	(user, password) when user press "change"
	None when user press "cancel" button '''
	dialog = CredentialsDialogController(user, password)
	return (
		(dialog.username, dialog.password)
		if dialog.show() == gtk.RESPONSE_ACCEPT
		else None
	)

