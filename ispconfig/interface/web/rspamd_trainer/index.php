<?php
require_once '../../lib/config.inc.php';
require_once '../../lib/app.inc.php';
require_once 'lib/broker.inc.php';

$app->auth->check_module_permissions('rspamd_trainer');
if(!$app->auth->is_admin()) {
    $app->error('Administrator access required.');
    exit;
}

$app->uses('tpl');
$app->tpl->newTemplate('form.tpl.htm');
$app->tpl->setInclude('content_tpl', 'templates/index.htm');

$language = $app->functions->check_language($_SESSION['s']['language']);
$lng_file = 'lib/lang/' . $language . '.lng';
if(!is_readable($lng_file)) {
    $lng_file = 'lib/lang/en.lng';
}
include $lng_file;

function rt_int_post($name, $minimum, $maximum) {
    if(!isset($_POST[$name]) || !preg_match('/^[0-9]+$/', (string)$_POST[$name])) {
        throw new Exception('Invalid numeric setting.');
    }
    $value = (int)$_POST[$name];
    if($value < $minimum || $value > $maximum) {
        throw new Exception('Numeric setting is outside the allowed range.');
    }
    return $value;
}

function rt_mailbox_id() {
    if(!isset($_GET['id']) || !preg_match('/^[1-9][0-9]*$/', (string)$_GET['id'])) {
        throw new Exception('Invalid mailbox ID.');
    }
    return (int)$_GET['id'];
}

$msg = '';
$error = '';
$action = isset($_GET['action']) ? (string)$_GET['action'] : '';

if($action !== '') {
    if($_SERVER['REQUEST_METHOD'] !== 'POST') {
        $error = $wb['post_required_txt'];
    } else {
        try {
            $app->auth->csrf_token_check();

            if($action === 'refresh') {
                rspamd_trainer_broker_result(array('op' => 'discovery', 'args' => array()));
                $msg = $wb['inventory_refreshed_txt'];
            } elseif($action === 'dry_run') {
                $result = rspamd_trainer_broker_result(array('op' => 'dry_run', 'args' => array()));
                $msg = sprintf(
                    $wb['dry_run_complete_txt'],
                    (int)$result['candidate_spam'],
                    (int)$result['candidate_ham']
                );
            } elseif($action === 'run') {
                rspamd_trainer_broker_result(array('op' => 'run_async', 'args' => array()));
                $msg = $wb['run_started_txt'];
            } elseif($action === 'policy_save') {
                $id = rt_mailbox_id();
                $mode_key = 'mode_' . $id;
                $age_key = 'age_days_' . $id;
                $batch_key = 'batch_size_' . $id;
                $allowed_modes = array('auto', 'imap', 'mixed', 'off');
                if(!isset($_POST[$mode_key]) || !in_array($_POST[$mode_key], $allowed_modes, true)) {
                    throw new Exception('Invalid mailbox mode.');
                }
                rspamd_trainer_broker_result(array(
                    'op' => 'policy_set',
                    'args' => array(
                        'mailbox_id' => $id,
                        'mode' => (string)$_POST[$mode_key],
                        'age_days' => rt_int_post($age_key, 30, 3650),
                        'batch_size' => rt_int_post($batch_key, 1, 1000),
                    ),
                ));
                $msg = $wb['policy_saved_txt'];
            } elseif($action === 'spam_enable') {
                $id = rt_mailbox_id();
                $confirm_key = 'confirm_spam_' . $id;
                if(!isset($_POST[$confirm_key]) || $_POST[$confirm_key] !== 'yes') {
                    throw new Exception($wb['spam_confirmation_required_txt']);
                }
                rspamd_trainer_broker_result(array(
                    'op' => 'spam_source_set',
                    'args' => array(
                        'mailbox_id' => $id,
                        'enabled' => true,
                        'archive_mailbox' => 'Trained',
                        'ham_mailbox' => 'Ham',
                    ),
                ));
                $msg = $wb['spam_source_enabled_txt'];
            } elseif($action === 'spam_disable') {
                $id = rt_mailbox_id();
                rspamd_trainer_broker_result(array(
                    'op' => 'spam_source_set',
                    'args' => array(
                        'mailbox_id' => $id,
                        'enabled' => false,
                        'archive_mailbox' => 'Trained',
                        'ham_mailbox' => 'Ham',
                    ),
                ));
                $msg = $wb['spam_source_disabled_txt'];
            } else {
                throw new Exception('Unknown action.');
            }
        } catch(Exception $e) {
            $error = $e->getMessage();
        }
    }
}

$health = array();
$status = array();
$inventory = array('mailboxes' => array(), 'access_modes' => array());
$classifier_available = false;

try {
    $health = rspamd_trainer_broker_result(array('op' => 'health', 'args' => array()));
    // Refresh the local inventory if the snapshot is available. A failed
    // refresh is shown as a warning but never falls back to direct DB access.
    try {
        rspamd_trainer_broker_result(array('op' => 'discovery', 'args' => array()));
    } catch(Exception $ignored) {
        if($error === '') {
            $error = $wb['inventory_refresh_failed_txt'];
        }
    }
    $status = rspamd_trainer_broker_result(array('op' => 'status', 'args' => array()));
    $inventory = rspamd_trainer_broker_result(array('op' => 'inventory_list', 'args' => array()));
    try {
        rspamd_trainer_broker_result(array('op' => 'classifier_stats', 'args' => array()));
        $classifier_available = true;
    } catch(Exception $ignored) {
        $classifier_available = false;
    }
} catch(Exception $e) {
    if($error === '') {
        $error = $e->getMessage();
    }
}

$dependencies = isset($status['dependencies']) && is_array($status['dependencies'])
    ? $status['dependencies']
    : array();

$healthy = !empty($health['ok'])
    && !empty($dependencies['inventory_source'])
    && !empty($dependencies['rspamd'])
    && !empty($dependencies['coordinator'])
    && !empty($dependencies['observer']);

$latest_run = isset($status['latest_run']) && is_array($status['latest_run'])
    ? $status['latest_run']
    : null;

$records = array();
if(isset($inventory['mailboxes']) && is_array($inventory['mailboxes'])) {
    foreach($inventory['mailboxes'] as $row) {
        $id = (int)$row['mailbox_id'];
        $policy = isset($row['policy']) && is_array($row['policy'])
            ? $row['policy']
            : array('mode' => 'auto', 'age_days' => 30, 'batch_size' => 100);

        $mode_options = '';
        $modes = array(
            'auto' => $wb['mode_auto_txt'],
            'imap' => $wb['mode_imap_txt'],
            'mixed' => $wb['mode_mixed_txt'],
            'off' => $wb['mode_off_txt'],
        );
        foreach($modes as $value => $label) {
            $selected = ((string)$policy['mode'] === $value) ? ' selected="selected"' : '';
            $mode_options .= '<option value="' . $value . '"' . $selected . '>'
                . htmlspecialchars($label, ENT_QUOTES, 'UTF-8') . '</option>';
        }

        $records[] = array(
            'id' => $id,
            'email' => htmlspecialchars((string)$row['email'], ENT_QUOTES, 'UTF-8'),
            'access_mode' => htmlspecialchars((string)$row['access_mode'], ENT_QUOTES, 'UTF-8'),
            'observed_access' => htmlspecialchars((string)$row['observed_access'], ENT_QUOTES, 'UTF-8'),
            'mode_options' => $mode_options,
            'age_days' => (int)$policy['age_days'],
            'batch_size' => (int)$policy['batch_size'],
            'eligible_txt' => !empty($row['aged_inbox_eligible']) ? $wb['yes_txt'] : $wb['no_txt'],
            'dedicated_spam_source' => !empty($row['dedicated_spam_source']) ? 1 : 0,
            'policy_is_default' => !empty($row['policy_is_default']) ? 1 : 0,
        );
    }
}

$app->tpl->setLoop('records', $records);
$app->tpl->setVar('overall_state', $healthy ? $wb['healthy_txt'] : $wb['needs_attention_txt']);
$app->tpl->setVar('overall_class', $healthy ? 'success' : 'warning');
$app->tpl->setVar('broker_state', !empty($health['ok']) ? $wb['available_txt'] : $wb['unavailable_txt']);
$app->tpl->setVar('inventory_state', !empty($dependencies['inventory_source']) ? $wb['available_txt'] : $wb['unavailable_txt']);
$app->tpl->setVar('rspamd_state', !empty($dependencies['rspamd']) ? $wb['available_txt'] : $wb['unavailable_txt']);
$app->tpl->setVar('observer_state', !empty($dependencies['observer']) ? $wb['available_txt'] : $wb['unavailable_txt']);
$app->tpl->setVar('classifier_state', $classifier_available ? $wb['available_txt'] : $wb['unavailable_txt']);
$app->tpl->setVar(
    'run_disabled',
    !empty($dependencies['async_run']) ? '' : ' disabled="disabled"'
);
$app->tpl->setVar('mailbox_count', isset($status['inventory_count']) ? (int)$status['inventory_count'] : 0);
$app->tpl->setVar('policy_count', isset($status['policy_count']) ? (int)$status['policy_count'] : 0);
$app->tpl->setVar('spam_source_count', isset($status['spam_source_count']) ? (int)$status['spam_source_count'] : 0);
$app->tpl->setVar(
    'latest_run',
    $latest_run
        ? htmlspecialchars(
            (string)$latest_run['status'] . ' / ' . (string)$latest_run['started_at'],
            ENT_QUOTES,
            'UTF-8'
        )
        : $wb['never_txt']
);
$app->tpl->setVar('msg', htmlspecialchars($msg, ENT_QUOTES, 'UTF-8'));
$app->tpl->setVar('error', htmlspecialchars($error, ENT_QUOTES, 'UTF-8'));
$app->tpl->setVar($wb);

$csrf_token = $app->auth->csrf_token_get('rspamd_trainer');
$app->tpl->setVar('_csrf_id', $csrf_token['csrf_id']);
$app->tpl->setVar('_csrf_key', $csrf_token['csrf_key']);

$app->tpl_defaults();
$app->tpl->pparse();
?>
