<?php
function rspamd_trainer_broker_call($request) {
    $socket_path = '/run/ispconfig-rspamd-trainer/broker.sock';
    $fp = @stream_socket_client('unix://' . $socket_path, $errno, $errstr, 2);
    if (!$fp) {
        throw new Exception('Rspamd trainer broker is unavailable.');
    }
    stream_set_timeout($fp, 30);

    $payload = json_encode($request);
    if ($payload === false) {
        fclose($fp);
        throw new Exception('Unable to encode broker request.');
    }

    $length = strlen($payload);
    $offset = 0;
    while ($offset < $length) {
        $written = fwrite($fp, substr($payload, $offset));
        if ($written === false || $written === 0) {
            fclose($fp);
            throw new Exception('Unable to write broker request.');
        }
        $offset += $written;
    }

    $response = fgets($fp, 65536);
    $meta = stream_get_meta_data($fp);
    fclose($fp);

    if ($response === false || !empty($meta['timed_out'])) {
        throw new Exception('No response from Rspamd trainer broker.');
    }

    $decoded = json_decode($response, true);
    if (!is_array($decoded)) {
        throw new Exception('Invalid response from Rspamd trainer broker.');
    }
    return $decoded;
}

function rspamd_trainer_broker_result($request) {
    $response = rspamd_trainer_broker_call($request);
    if (empty($response['ok'])) {
        $message = isset($response['message']) ? (string)$response['message'] : 'Broker operation failed.';
        throw new Exception($message);
    }
    if (!array_key_exists('result', $response)) {
        throw new Exception('Broker response did not contain a result.');
    }
    return $response['result'];
}
?>
