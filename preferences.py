import sublime_plugin


PACKAGE_NAME = __package__.split(".", 1)[0]


class JumperEditSettingsCommand(sublime_plugin.WindowCommand):
    def run(self, base_file, default, user_file=None):
        args = {
            "base_file": "${packages}/" + PACKAGE_NAME + "/" + base_file,
            "default": default,
        }
        if user_file is not None:
            args["user_file"] = user_file

        self.window.run_command("edit_settings", args)
