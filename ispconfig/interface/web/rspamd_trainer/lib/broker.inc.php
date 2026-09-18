<?php
function rspamd_trainer_broker_call($request) {
    $socket_path = '/run/ispconfig-rspamd-trainer/broker.sock';
    $fp = @stream_socket_client('unix://' . $socket_path, $errno, $errstr, 2);
    if (!$fp) {
        throw new Exception('Rspamd trainer broker is unavailable.');
    }
    stream_set_timeout($fp, 3);
    fwrite($fp, json_encode($request));
    $response = fgets($fp, 65536);
    fclose($fp);
    if ($response === false) {
        throw new Exception('No response from Rspamd trainer broker.');
    }
    $decoded = json_decode($response, true);
    if (!is_array($decoded)) {
        throw new Exception('Invalid response from Rspamd trainer broker.');
    }
    return $decoded;
}
?>
