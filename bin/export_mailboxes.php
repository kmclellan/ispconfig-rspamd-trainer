<?php
/**
 * Export the minimal ISPConfig mailbox inventory required by the trainer.
 *
 * This helper is intentionally narrow. It reads ISPConfig's own database
 * credentials, selects only mailbox identity/protocol capability fields, and
 * atomically writes a JSON snapshot. It never exports passwords, names,
 * forwarding data, message content, or maildir paths.
 *
 * Usage:
 *   php export_mailboxes.php OUTPUT_JSON [ISPConfig config.inc.php]
 */

if($argc < 2 || $argc > 3) {
    fwrite(STDERR, "usage: php export_mailboxes.php OUTPUT_JSON [config.inc.php]\n");
    exit(2);
}

$output = $argv[1];
$config = $argc === 3
    ? $argv[2]
    : '/usr/local/ispconfig/interface/lib/config.inc.php';

if($output === '' || $output[0] !== '/' || strpos($output, "\0") !== false) {
    fwrite(STDERR, "ERROR: output path must be absolute\n");
    exit(2);
}
$parent = dirname($output);
if(!is_dir($parent) || !is_writable($parent)) {
    fwrite(STDERR, "ERROR: output directory is not writable\n");
    exit(1);
}
if(!is_readable($config)) {
    fwrite(STDERR, "ERROR: ISPConfig config is not readable\n");
    exit(1);
}

require $config;
if(!isset($conf) || !is_array($conf) || empty($conf['db_host'])) {
    fwrite(STDERR, "ERROR: ISPConfig database configuration unavailable\n");
    exit(1);
}

if(function_exists('mysqli_report')) {
    mysqli_report(MYSQLI_REPORT_OFF);
}

$port = isset($conf['db_port']) ? (int)$conf['db_port'] : 3306;
try {
    $db = @new mysqli(
        $conf['db_host'],
        $conf['db_user'],
        $conf['db_password'],
        $conf['db_database'],
        $port
    );
} catch(\Throwable $e) {
    $db = false;
}
if(!$db || $db->connect_errno) {
    fwrite(STDERR, "ERROR: ISPConfig database connection failed\n");
    exit(1);
}

$charset = !empty($conf['db_charset']) ? $conf['db_charset'] : 'utf8mb4';
if(!@$db->set_charset($charset) && $charset !== 'utf8mb4') {
    @$db->set_charset('utf8mb4');
}

$sql = "SELECT mailuser_id, server_id, email, disableimap, disablepop3, " .
       "access, disabledoveadm FROM mail_user ORDER BY mailuser_id";
$result = $db->query($sql);
if(!$result) {
    fwrite(STDERR, "ERROR: mailbox inventory query failed\n");
    exit(1);
}

$rows = array();
while($row = $result->fetch_assoc()) {
    $rows[] = array(
        'mailuser_id' => (int)$row['mailuser_id'],
        'server_id' => (int)$row['server_id'],
        'email' => (string)$row['email'],
        'disableimap' => (string)$row['disableimap'],
        'disablepop3' => (string)$row['disablepop3'],
        'access' => (string)$row['access'],
        'disabledoveadm' => (string)$row['disabledoveadm'],
    );
}
$db->close();

$payload = array(
    'schema' => 1,
    'generated_at' => gmdate('c'),
    'mailboxes' => $rows,
);
$json = json_encode(
    $payload,
    JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT
);
if($json === false) {
    fwrite(STDERR, "ERROR: JSON encoding failed\n");
    exit(1);
}
$json .= "\n";

$tmp = tempnam($parent, '.mailboxes.');
if($tmp === false) {
    fwrite(STDERR, "ERROR: unable to create temporary snapshot\n");
    exit(1);
}

$ok = false;
try {
    if(file_put_contents($tmp, $json, LOCK_EX) === false) {
        throw new RuntimeException('snapshot write failed');
    }
    if(!chmod($tmp, 0640)) {
        throw new RuntimeException('snapshot chmod failed');
    }
    if(!rename($tmp, $output)) {
        throw new RuntimeException('snapshot rename failed');
    }
    $ok = true;
} catch(\Throwable $e) {
    fwrite(STDERR, "ERROR: mailbox snapshot write failed\n");
} finally {
    if(!$ok && file_exists($tmp)) {
        @unlink($tmp);
    }
}

exit($ok ? 0 : 1);
