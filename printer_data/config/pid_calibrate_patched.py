# Calibration of heater PID settings
#
# Copyright (C) 2016-2018  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math, logging, os, re
from . import heaters

class PIDCalibrate:
    def __init__(self, config):
        self.printer = config.get_printer()
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('PID_CALIBRATE', self.cmd_PID_CALIBRATE,
                               desc=self.cmd_PID_CALIBRATE_help)
        gcode.register_command('SET_HEATER_PID', self.cmd_SET_HEATER_PID,
                               desc=self.cmd_SET_HEATER_PID_help)
    cmd_PID_CALIBRATE_help = "Run PID calibration test"
    def cmd_PID_CALIBRATE(self, gcmd):
        heater_name = gcmd.get('HEATER')
        target = gcmd.get_float('TARGET')
        write_file = gcmd.get_int('WRITE_FILE', 0)
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(heater_name)
        except self.printer.config_error as e:
            raise gcmd.error(str(e))
        self.printer.lookup_object('toolhead').get_last_move_time()
        calibrate = ControlAutoTune(heater, target)
        old_control = heater.set_control(calibrate)
        try:
            pheaters.set_temperature(heater, target, True)
        except self.printer.command_error as e:
            heater.set_control(old_control)
            raise
        heater.set_control(old_control)
        if write_file:
            calibrate.write_file('/tmp/heattest.txt')
        if calibrate.check_busy(0., 0., 0.):
            raise gcmd.error("pid_calibrate interrupted")
        # Log and report results
        Kp, Ki, Kd = calibrate.calc_final_pid()
        logging.info("Autotune: final: Kp=%f Ki=%f Kd=%f", Kp, Ki, Kd)
        # If _pid_profiles macro exists, determine which profile to update.
        profile_section = 'gcode_macro _pid_profiles'
        prefix = None
        pid_profiles_obj = self.printer.lookup_object(profile_section, None)
        if pid_profiles_obj is not None:
            variables = pid_profiles_obj.variables
            if heater_name == 'extruder':
                threshold = float(variables.get('extruder_threshold', 250.))
                prefix = 'extruder_high' if target >= threshold else 'extruder_standard'
            elif heater_name == 'heater_bed':
                threshold = float(variables.get('bed_threshold', 85.))
                prefix = 'bed_high' if target > threshold else 'bed_standard'
        if prefix is not None:
            # Write directly to pid_profiles.cfg so values land in one place.
            written = False
            try:
                config_file = self.printer.get_start_args()['config_file']
                profiles_path = os.path.join(
                    os.path.dirname(config_file), 'pid_profiles.cfg')
                if os.path.isfile(profiles_path):
                    with open(profiles_path, 'r') as f:
                        content = f.read()
                    for suffix, val in [('kp', Kp), ('ki', Ki), ('kd', Kd)]:
                        pattern = r'(variable_%s_%s\s*:\s*)[\d.]+' % (prefix, suffix)
                        content, n = re.subn(pattern,
                                             r'\g<1>%.3f' % val, content)
                        if n == 0:
                            raise ValueError(
                                "variable_%s_%s not found in pid_profiles.cfg"
                                % (prefix, suffix))
                    with open(profiles_path, 'w') as f:
                        f.write(content)
                    written = True
            except Exception as e:
                logging.warning("pid_calibrate: could not write pid_profiles.cfg: %s", e)
            if written:
                gcmd.respond_info(
                    "PID parameters: pid_Kp=%.3f pid_Ki=%.3f pid_Kd=%.3f\n"
                    "Profile '%s' written to pid_profiles.cfg.\n"
                    "Run FIRMWARE_RESTART to apply." % (Kp, Ki, Kd, prefix))
            else:
                # Fall back: stage for SAVE_CONFIG
                configfile = self.printer.lookup_object('configfile')
                gcmd.respond_info(
                    "PID parameters: pid_Kp=%.3f pid_Ki=%.3f pid_Kd=%.3f\n"
                    "The SAVE_CONFIG command will update the '%s' PID profile\n"
                    "with these parameters and restart the printer." % (Kp, Ki, Kd, prefix))
                configfile.set(profile_section, 'variable_%s_kp' % prefix, "%.3f" % (Kp,))
                configfile.set(profile_section, 'variable_%s_ki' % prefix, "%.3f" % (Ki,))
                configfile.set(profile_section, 'variable_%s_kd' % prefix, "%.3f" % (Kd,))
        else:
            gcmd.respond_info(
                "PID parameters: pid_Kp=%.3f pid_Ki=%.3f pid_Kd=%.3f\n"
                "The SAVE_CONFIG command will update the printer config file\n"
                "with these parameters and restart the printer." % (Kp, Ki, Kd))
            cfgname = heater.get_name()
            configfile = self.printer.lookup_object('configfile')
            configfile.set(cfgname, 'control', 'pid')
            configfile.set(cfgname, 'pid_Kp', "%.3f" % (Kp,))
            configfile.set(cfgname, 'pid_Ki', "%.3f" % (Ki,))
            configfile.set(cfgname, 'pid_Kd', "%.3f" % (Kd,))
    cmd_SET_HEATER_PID_help = "Sets a heater PID parameter"
    def cmd_SET_HEATER_PID(self, gcmd):
        heater_name = gcmd.get('HEATER')
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(heater_name)
        except self.printer.config_error as e:
            raise gcmd.error(str(e))
        # Sovol's fork stores control as heater.control; standard Klipper uses get_control()
        if hasattr(heater, 'get_control'):
            control = heater.get_control()
        elif hasattr(heater, 'control'):
            control = heater.control
        else:
            raise gcmd.error("Cannot access heater control object")
        pid_base = getattr(heaters, 'PID_PARAM_BASE', 255.)
        pid_cls = getattr(heaters, 'ControlPID', None)
        if pid_cls is not None and not isinstance(control, pid_cls):
            raise gcmd.error("Not a PID controlled heater")
        # Internal storage: control.Kp = config_Kp / pid_base — so default shown is config scale
        cur_Kp = getattr(control, 'Kp', 0.)
        cur_Ki = getattr(control, 'Ki', 0.)
        cur_Kd = getattr(control, 'Kd', 0.)
        Kp = gcmd.get_float('KP', cur_Kp * pid_base)
        Ki = gcmd.get_float('KI', cur_Ki * pid_base)
        Kd = gcmd.get_float('KD', cur_Kd * pid_base)
        logging.info("Setting heater %s parameters: Kp=%f Ki=%f Kd=%f",
                     heater_name, Kp, Ki, Kd)
        control.Kp = Kp / pid_base
        control.Ki = Ki / pid_base
        control.Kd = Kd / pid_base

TUNE_PID_DELTA = 5.0

class ControlAutoTune:
    def __init__(self, heater, target):
        self.heater = heater
        self.heater_max_power = heater.get_max_power()
        self.calibrate_temp = target
        # Heating control
        self.heating = False
        self.peak = 0.
        self.peak_time = 0.
        # Peak recording
        self.peaks = []
        # Sample recording
        self.last_pwm = 0.
        self.pwm_samples = []
        self.temp_samples = []
    # Heater control
    def set_pwm(self, read_time, value):
        if value != self.last_pwm:
            self.pwm_samples.append(
                (read_time + self.heater.get_pwm_delay(), value))
            self.last_pwm = value
        self.heater.set_pwm(read_time, value)
    def temperature_update(self, read_time, temp, target_temp):
        self.temp_samples.append((read_time, temp))
        # Check if the temperature has crossed the target and
        # enable/disable the heater if so.
        if self.heating and temp >= target_temp:
            self.heating = False
            self.check_peaks()
            self.heater.alter_target(self.calibrate_temp - TUNE_PID_DELTA)
        elif not self.heating and temp <= target_temp:
            self.heating = True
            self.check_peaks()
            self.heater.alter_target(self.calibrate_temp)
        # Check if this temperature is a peak and record it if so
        if self.heating:
            self.set_pwm(read_time, self.heater_max_power)
            if temp < self.peak:
                self.peak = temp
                self.peak_time = read_time
        else:
            self.set_pwm(read_time, 0.)
            if temp > self.peak:
                self.peak = temp
                self.peak_time = read_time
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        if self.heating or len(self.peaks) < 12:
            return True
        return False
    # Analysis
    def check_peaks(self):
        self.peaks.append((self.peak, self.peak_time))
        if self.heating:
            self.peak = 9999999.
        else:
            self.peak = -9999999.
        if len(self.peaks) < 4:
            return
        self.calc_pid(len(self.peaks)-1)
    def calc_pid(self, pos):
        temp_diff = self.peaks[pos][0] - self.peaks[pos-1][0]
        time_diff = self.peaks[pos][1] - self.peaks[pos-2][1]
        # Use Astrom-Hagglund method to estimate Ku and Tu
        amplitude = .5 * abs(temp_diff)
        Ku = 4. * self.heater_max_power / (math.pi * amplitude)
        Tu = time_diff
        # Use Ziegler-Nichols method to generate PID parameters
        Ti = 0.5 * Tu
        Td = 0.125 * Tu
        Kp = 0.6 * Ku * heaters.PID_PARAM_BASE
        Ki = Kp / Ti
        Kd = Kp * Td
        logging.info("Autotune: raw=%f/%f Ku=%f Tu=%f  Kp=%f Ki=%f Kd=%f",
                     temp_diff, self.heater_max_power, Ku, Tu, Kp, Ki, Kd)
        return Kp, Ki, Kd
    def calc_final_pid(self):
        cycle_times = [(self.peaks[pos][1] - self.peaks[pos-2][1], pos)
                       for pos in range(4, len(self.peaks))]
        midpoint_pos = sorted(cycle_times)[len(cycle_times)//2][1]
        return self.calc_pid(midpoint_pos)
    # Offline analysis helper
    def write_file(self, filename):
        pwm = ["pwm: %.3f %.3f" % (time, value)
               for time, value in self.pwm_samples]
        out = ["%.3f %.3f" % (time, temp) for time, temp in self.temp_samples]
        f = open(filename, "w")
        f.write('\n'.join(pwm + out))
        f.close()

def load_config(config):
    return PIDCalibrate(config)
