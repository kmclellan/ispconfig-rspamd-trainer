<?php
/**
 * Remove the rspamd_trainer module from ISPConfig users.
 *
 * Adapted from ispconfig-theme-customizer/bin/unassign_module.php.
 * Copyright (c) 2026 Wade Beckett.
 * Modifications copyright (c) 2026 Kelly McLellan.
 * MIT License. See ../THIRD_PARTY_NOTICES.md and ../LICENSE.
 *
 * The installer assigns the module only to administrators, but an
 * administrator may later assign it manually to another control-panel user.
 * Uninstall therefore scans all users. It also resets startmodule to dashboard
 * where necessary so a removed module cannot leave a broken login redirect.
 *
 * Usage:
 *   php unassign_module.php [/usr/local/ispconfig/interface/lib/config.inc.php]
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

$res = $m->query("SELECT userid, username, modules, startmodule FROM sys_user");
if(!$res) {
    fwrite(STDERR, "ERROR: query failed: " . $m->error . "\n");
    exit(1);
}

$changed = 0;
while($r = $res->fetch_assoc()) {
    $mods = array_values(
        array_filter(array_map('trim', explode(',', (string)$r['modules'])), 'strlen')
    );
    $new_mods = array_values(
        array_filter($mods, function($x) { return $x !== 'rspamd_trainer'; })
    );
    $new_start = ((string)$r['startmodule'] === 'rspamd_trainer')
        ? 'dashboard'
        : (string)$r['startmodule'];

    if($new_mods !== $mods || $new_start !== (string)$r['startmodule']) {
        $csv = implode(',', $new_mods);
        $uid = (int)$r['userid'];
        $stmt = $m->prepare(
            "UPDATE sys_user SET modules = ?, startmodule = ? WHERE userid = ?"
        );
        if(!$stmt) {
            fwrite(STDERR, "ERROR: prepare failed: " . $m->error . "\n");
            exit(1);
        }
        $stmt->bind_param('ssi', $csv, $new_start, $uid);
        if(!$stmt->execute()) {
            fwrite(
                STDERR,
                "ERROR: update failed for user '" . $r['username'] . "': " .
                $stmt->error . "\n"
            );
            exit(1);
        }
        $stmt->close();
        echo "  - removed 'rspamd_trainer' from user '" . $r['username'] . "'";
        if($new_start !== (string)$r['startmodule']) {
            echo " (startmodule reset to dashboard)";
        }
        echo "\n";
        $changed++;
    }
}

if($changed === 0) {
    echo "  no user had the 'rspamd_trainer' module assigned\n";
}
echo "  NOTE: module lists are session-cached; active sessions see the change at next login\n";

$m->close();
