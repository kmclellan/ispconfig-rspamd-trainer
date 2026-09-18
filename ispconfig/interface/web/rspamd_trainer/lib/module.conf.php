<?php

$module['name'] = 'rspamd_trainer';
$module['title'] = 'Rspamd Training';
$module['template'] = 'module.tpl.htm';
$module['startpage'] = 'rspamd_trainer/index.php';
$module['tab_width'] = '';
$module['order'] = '95';
$module['icon'] = 'icon icon-mail';

$items = array();
$items[] = array(
    'title' => 'Overview',
    'target' => 'content',
    'link' => 'rspamd_trainer/index.php',
    'html_id' => 'rspamd_trainer_overview'
);

$module['nav'][] = array(
    'title' => 'Rspamd Training',
    'open' => 1,
    'items' => $items
);

unset($items);
?>
