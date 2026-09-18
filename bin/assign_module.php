<?php
/**
 * Assign the rspamd_trainer module to ISPConfig admin users.
 *
 * Adapted from ispconfig-theme-customizer/bin/assign_module.php.
 * Copyright (c) 2026 Wade Beckett.
 * Modifications copyright (c) 2026 Kelly McLellan.
 * MIT License. See ../THIRD_PARTY_NOTICES.md and ../LICENSE.
 *
 * Usage:
 *   php assign_module.php [/usr/local/ispconfig/interface/lib/config.inc.php]
 */

$conf_path = isset($argv[1]) ? $argv[1] : '/usr/local/ispconfig/interface/lib/config.inc.php';
if(!is_readable($conf_path)) {
    fwrite(STDERR, "ERROR: ISPConfig config not readable: $conf_path\n");
    exit(1);
}
require $conf_path;
if(!isset($conf) || !is_array($conf) || empty($conf['db_host'])) {
    fwrite(STDERR, "ERROR: no database configuration found in $conf_path\n");
    exit(1);
}

if(function_exists('mysqli_report')) {
    mysqli_report(MYSQLI_REPORT_OFF);
}

$port = isset($conf['db_port']) ? (int)$conf['db_port'] : 3306;
try {
    $m = @new mysqli(
        $conf['db_host'],
        $conf['db_user'],
        $conf['db_password'],
        $conf['db_database'],
        $port
    );
} catch(\Throwable $e) {
    $m = false;
}
if(!$m || $m->connect_errno) {
    fwrite(
        STDERR,
        "ERROR: database connection failed" .
        ($m ? ": " . $m->connect_error : "") . "\n"
    );
    exit(1);
}

$db_charset = !empty($conf['db_charset']) ? $conf['db_charset'] : 'utf8mb4';
if(!@$m->set_charset($db_charset) && $db_charset !== 'utf8mb4') {
    @$m->set_charset('utf8mb4');
}

$res = $m->query("SELECT userid, username, modules FROM sys_user WHERE typ = 'admin'");
if(!$res) {
    fwrite(STDERR, "ERROR: query failed: " . $m->error . "\n");
    exit(1);
}

$changed = 0;
while($r = $res->fetch_assoc()) {
    $mods = array_values(
        array_filter(array_map('trim', explode(',', (string)$r['modules'])), 'strlen')
    );
    if(!in_array('rspamd_trainer', $mods, true)) {
        $mods[] = 'rspamd_trainer';
        $csv = implode(',', $mods);
        $uid = (int)$r['userid'];
        $stmt = $m->prepare("UPDATE sys_user SET modules = ? WHERE userid = ?");
        if(!$stmt) {
            fwrite(STDERR, "ERROR: prepare failed: " . $m->error . "\n");
            exit(1);
        }
        $stmt->bind_param('si', $csv, $uid);
        if(!$stmt->execute()) {
            fwrite(
                STDERR,
                "ERROR: update failed for user '" . $r['username'] . "': " .
                $stmt->error . "\n"
            );
            exit(1);
        }
        $stmt->close();
        echo "  + assigned 'rspamd_trainer' to admin user '" .
             $r['username'] . "'\n";
        $changed++;
    }
}

if($changed === 0) {
    echo "  all admin users already have the 'rspamd_trainer' module\n";
}

$m->close();
