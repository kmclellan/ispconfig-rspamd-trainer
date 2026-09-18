<?php
require_once '../../lib/config.inc.php';
require_once '../../lib/app.inc.php';
require_once 'lib/broker.inc.php';

$app->auth->check_module_permissions('rspamd_trainer');
if (!$app->auth->is_admin()) {
    $app->error('Administrator access required.');
    exit;
}

$app->uses('tpl');
$app->tpl->newTemplate('form.tpl.htm');
$app->tpl->setInclude('content_tpl', 'templates/index.htm');

$status = array('ok' => false, 'error' => 'Not checked');
$policies = array();

try {
    $status = rspamd_trainer_broker_call(array('op' => 'health', 'args' => array()));
    $policy_response = rspamd_trainer_broker_call(array('op' => 'policy_list', 'args' => array()));
    if (!empty($policy_response['ok']) && isset($policy_response['result']['policies'])) {
        $policies = $policy_response['result']['policies'];
    }
} catch (Exception $e) {
    $status = array('ok' => false, 'error' => $e->getMessage());
}

$app->tpl->setVar('broker_ok', !empty($status['ok']) ? 'Yes' : 'No');
$app->tpl->setVar(
    'broker_message',
    isset($status['error']) ? htmlspecialchars($status['error'], ENT_QUOTES, 'UTF-8') : 'Connected'
);
$app->tpl->setVar('policy_count', count($policies));
$app->tpl_defaults();
$app->tpl->pparse();
?>
