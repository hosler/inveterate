<!DOCTYPE html>
<html lang="en" class="noVNC_loading">
<head>

    <!--
    noVNC example: simple example using default UI
    Copyright (C) 2018 The noVNC Authors
    noVNC is licensed under the MPL 2.0 (see LICENSE.txt)
    This file is licensed under the 2-Clause BSD license (see LICENSE.txt).

    Connect parameters are provided in query string:
        http://example.com/?host=HOST&port=PORT&encrypt=1
    or the fragment:
        http://example.com/#host=HOST&port=PORT&encrypt=1
    -->
    <title>[% nodename %] - Proxmox Console</title>

    <meta charset="utf-8">

    <!-- Apple iOS Safari settings -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <!-- Stylesheets -->
    <link rel="stylesheet" href="/novnc/app/styles/base.css?ver=1.1.0-1" />
    <link rel="stylesheet" href="/novnc/app/styles/pve.css?ver=1.1.0-1" />

    <!-- this is included as a normal file in order to catch script-loading errors as well -->
    <script type="text/javascript" src="/novnc/app/error-handler.js?ver=1.1.0-1"></script>
    <script type="text/javascript">
	if (typeof(PVE) === 'undefined') PVE = {};
	PVE.UserName = '[% username %]';
	PVE.CSRFPreventionToken = '[% token %]';
	INCLUDE_URI='/novnc/include';
    </script>

    <!-- begin scripts -->
    <script crossorigin=anonymous" src="/novnc/app.js?ver=1.1.0-1"></script>
    <!-- end scripts -->
</head>

<body>

    <div id="noVNC_fallback_error" class="noVNC_center">
        <div>
            <div>noVNC encountered an error:</div>
            <br>
            <div id="noVNC_fallback_errormsg"></div>
        </div>
    </div>

    <!-- noVNC Control Bar -->
    <div id="noVNC_control_bar_anchor" class="noVNC_vcenter">

        <div id="noVNC_control_bar">
            <div id="noVNC_control_bar_handle" title="Hide/Show the control bar"><div></div></div>

            <div class="noVNC_scroll">

            <h1 class="noVNC_logo" translate="no"><span>no</span><br>VNC</h1>

            <!-- Drag/Pan the viewport -->
            <input type="image" alt="viewport drag" src="/novnc/app/images/drag.svg"
                id="noVNC_view_drag_button" class="noVNC_button noVNC_hidden"
                title="Move/Drag Viewport">

            <!--noVNC Touch Device only buttons-->
            <div id="noVNC_mobile_buttons">
                <input type="image" alt="No mousebutton" src="/novnc/app/images/mouse_none.svg"
                    id="noVNC_mouse_button0" class="noVNC_button"
                    title="Active Mouse Button">
                <input type="image" alt="Left mousebutton" src="/novnc/app/images/mouse_left.svg"
                    id="noVNC_mouse_button1" class="noVNC_button"
                    title="Active Mouse Button">
                <input type="image" alt="Middle mousebutton" src="/novnc/app/images/mouse_middle.svg"
                    id="noVNC_mouse_button2" class="noVNC_button"
                    title="Active Mouse Button">
                <input type="image" alt="Right mousebutton" src="/novnc/app/images/mouse_right.svg"
                    id="noVNC_mouse_button4" class="noVNC_button"
                    title="Active Mouse Button">
                <input type="image" alt="Keyboard" src="/novnc/app/images/keyboard.svg"
                    id="noVNC_keyboard_button" class="noVNC_button" title="Show Keyboard">
            </div>

            <!-- Extra manual keys -->
            <div id="noVNC_extra_keys">
                <input type="image" alt="Extra keys" src="/novnc/app/images/toggleextrakeys.svg"
                    id="noVNC_toggle_extra_keys_button" class="noVNC_button"
                    title="Show Extra Keys">
                <div class="noVNC_vcenter">
                <div id="noVNC_modifiers" class="noVNC_panel">
                    <input type="image" alt="Ctrl" src="/novnc/app/images/ctrl.svg"
                        id="noVNC_toggle_ctrl_button" class="noVNC_button"
                        title="Toggle Ctrl">
                    <input type="image" alt="Alt" src="/novnc/app/images/alt.svg"
                        id="noVNC_toggle_alt_button" class="noVNC_button"
                        title="Toggle Alt">
                    <input type="image" alt="Alt" src="/novnc/app/images/windows.svg"
                        id="noVNC_toggle_windows_button" class="noVNC_button"
                        title="Toggle Windows">
                    <input type="image" alt="Tab" src="/novnc/app/images/tab.svg"
                        id="noVNC_send_tab_button" class="noVNC_button"
                        title="Send Tab">
                    <input type="image" alt="Esc" src="/novnc/app/images/esc.svg"
                        id="noVNC_send_esc_button" class="noVNC_button"
                        title="Send Escape">
                    <input type="image" alt="Ctrl+Alt+Del" src="/novnc/app/images/ctrlaltdel.svg"
                        id="noVNC_send_ctrl_alt_del_button" class="noVNC_button"
                        title="Send Ctrl-Alt-Del">
                </div>
                </div>
            </div>

            <!-- Shutdown/Reboot -->
            <input type="image" alt="Shutdown/Reboot" src="/novnc/app/images/power.svg"
                id="noVNC_power_button" class="noVNC_button"
                title="Shutdown/Reboot...">
            <div class="noVNC_vcenter">
            <div id="noVNC_power" class="noVNC_panel">
                <div class="noVNC_heading">
                    <img alt="" src="/novnc/app/images/power.svg"> Power
                </div>
                <input type="button" id="noVNC_shutdown_button" value="Shutdown">
                <input type="button" id="noVNC_reboot_button" value="Reboot">
                <input type="button" id="noVNC_reset_button" value="Reset">
            </div>
            </div>

            <!-- Clipboard -->
            <input type="image" alt="Clipboard" src="/novnc/app/images/clipboard.svg"
                id="noVNC_clipboard_button" class="noVNC_button"
                title="Clipboard">
            <div class="noVNC_vcenter">
            <div id="noVNC_clipboard" class="noVNC_panel">
                <div class="noVNC_heading">
                    <img alt="" src="/novnc/app/images/clipboard.svg"> Clipboard
                </div>
                <textarea id="noVNC_clipboard_text" rows=5></textarea>
                <br>
                <input id="noVNC_clipboard_clear_button" type="button"
                    value="Clear" class="noVNC_submit">
            </div>
            </div>

            <!-- Toggle fullscreen -->
            <input type="image" alt="Fullscreen" src="/novnc/app/images/fullscreen.svg"
                id="noVNC_fullscreen_button" class="noVNC_button noVNC_hidden"
                title="Fullscreen">

            <!-- Settings -->
            <input type="image" alt="Settings" src="/novnc/app/images/settings.svg"
                id="noVNC_settings_button" class="noVNC_button"
                title="Settings">
            <div class="noVNC_vcenter">
            <div id="noVNC_settings" class="noVNC_panel">
                <ul>
                    <li class="noVNC_heading">
                        <img alt="" src="/novnc/app/images/settings.svg"> Settings
                    </li>
                    <li style="display:none;">
                        <label><input id="noVNC_setting_shared" type="checkbox"> Shared Mode</label>
                    </li>
                    <li>
                        <label><input id="noVNC_setting_view_only" type="checkbox"> View Only</label>
                    </li>
                    <li><hr></li>
                    <li>
                        <label><input id="noVNC_setting_view_clip" type="checkbox"> Clip to Window</label>
                    </li>
                    <li>
                        <label><input id="noVNC_setting_local_cursor" type="checkbox" /> Local Cursor</label>
                    </li>
                    <li>
                        <label><input id="noVNC_setting_autoresize" type="checkbox" /> Autoresize Window</label>
                    </li>
                    <li>
                        <label for="noVNC_setting_resize">Scaling Mode:</label>
                        <select id="noVNC_setting_resize" name="vncResize">
                            <option value="off">Off</option>
                            <option value="scale">Local Scaling</option>
                        </select>
                    </li>
                    <li><hr></li>
                    <li style="display:none;">
                        <div class="noVNC_expander">Advanced</div>
                        <div><ul>
                            <li>
                                <label for="noVNC_setting_repeaterID">Repeater ID:</label>
                                <input id="noVNC_setting_repeaterID" type="text" value="">
                            </li>
                            <li>
                                <div class="noVNC_expander">WebSocket</div>
                                <div><ul>
                                    <li>
                                        <label><input id="noVNC_setting_encrypt" type="checkbox"> Encrypt</label>
                                    </li>
                                    <li>
                                        <label for="noVNC_setting_host">Host:</label>
                                        <input id="noVNC_setting_host">
                                    </li>
                                    <li>
                                        <label for="noVNC_setting_port">Port:</label>
                                        <input id="noVNC_setting_port" type="number">
                                    </li>
                                    <li>
                                        <label for="noVNC_setting_path">Path:</label>
                                        <input id="noVNC_setting_path" type="text" value="websockify">
                                    </li>
                                </ul></div>
                            </li>
                            <li><hr></li>
                            <li>
                                <label><input id="noVNC_setting_reconnect" type="checkbox"> Automatic Reconnect</label>
                            </li>
                            <li>
                                <label for="noVNC_setting_reconnect_delay">Reconnect Delay (ms):</label>
                                <input id="noVNC_setting_reconnect_delay" type="number">
                            </li>
                            <li><hr></li>
                            <li>
                                <label><input id="noVNC_setting_show_dot" type="checkbox"> Show Dot when No Cursor</label>
                            </li>
                            <li><hr></li>
                            <!-- Logging selection dropdown -->
                            <li>
                                <label>Logging:
                                    <select id="noVNC_setting_logging" name="vncLogging">
                                    </select>
                                </label>
                            </li>
                        </ul></div>
                    </li>
                </ul>
            </div>
            </div>

	    <!-- PVE Commands -->
            <input type="image" alt="Commands" src="/novnc/app/images/power.svg"
                id="pve_commands_button" class="noVNC_button"
                title="Commands" />

            <div class="noVNC_vcenter">
            <div id="pve_commands" class="noVNC_panel">
                <div class="noVNC_heading">
                    <img src="/novnc/app/images/power.svg"> Commands
                </div>
		<input id="pve_command_start" type="button" value="Start" />
		<input id="pve_command_shutdown" type="button" value="Shutdown" />
		<input id="pve_command_stop" type="button" value="Stop" />
		<input id="pve_command_reset" type="button" value="Reset" />
		<input id="pve_command_suspend" type="button" value="Suspend" />
		<input id="pve_command_resume" type="button" value="Resume" />
		<input id="pve_command_reload" type="button" value="Reload" />
	    </div>
	    </div>


            <!-- Connection Controls -->
            <input type="image" alt="Disconnect" src="/novnc/app/images/disconnect.svg"
                id="noVNC_disconnect_button" class="noVNC_button"
                title="Disconnect">

            </div>
        </div>

        <div id="noVNC_control_bar_hint"></div>

    </div> <!-- End of noVNC_control_bar -->

    <!-- Status Dialog -->
    <div id="noVNC_status"></div>

    <!-- Connect button -->
    <div class="noVNC_center">
        <div id="noVNC_connect_dlg">
            <div class="noVNC_logo" translate="no"><span>no</span>VNC</div>
            <div id="noVNC_connect_button"><div>
                <img alt="" src="/novnc/app/images/connect.svg"> Connect
            </div></div>
        </div>
    </div>

    <!-- Password Dialog -->
    <div class="noVNC_center noVNC_connect_layer">
    <div id="noVNC_password_dlg" class="noVNC_panel"><form>
        <ul>
            <li>
                <label>Password:</label>
                <input id="noVNC_password_input" type="password">
            </li>
            <li>
                <input id="noVNC_password_button" type="submit" value="Send Password" class="noVNC_submit">
            </li>
        </ul>
    </form></div>
    </div>

    <!-- Transition Screens -->
    <div id="noVNC_transition">
        <div id="noVNC_transition_text"></div>
        <div>
        <input type="button" id="noVNC_cancel_reconnect_button" value="Cancel" class="noVNC_submit">
        </div>
        <div class="noVNC_spinner"></div>
    </div>

    <!-- This is where the RFB elements will attach -->
    <div id="noVNC_container">
        <!-- Note that Google Chrome on Android doesn't respect any of these,
             html attributes which attempt to disable text suggestions on the
             on-screen keyboard. Let's hope Chrome implements the ime-mode
             style for example -->
        <textarea id="noVNC_keyboardinput" autocapitalize="off"
            autocomplete="off" spellcheck="false" tabindex="-1"></textarea>
    </div>

    <audio id="noVNC_bell">
        <source src="/novnc/app/sounds/bell.oga" type="audio/ogg">
        <source src="/novnc/app/sounds/bell.mp3" type="audio/mpeg">
    </audio>
 </body>
</html>
