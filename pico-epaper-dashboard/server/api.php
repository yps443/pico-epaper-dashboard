<?php
/**
 * 墨水屏统一服务端 API v2
 * GET  /api.php?action=all              → 余额 + 待办
 * POST /api.php?action=todos            → 保存待办 (body: {"todos":["a","b"]})
 * POST /api.php?action=done&idx=0       → 标记完成
 * POST /api.php?action=undone&idx=0     → 取消完成
 * POST /api.php?action=clear_done       → 清除已完成
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$DATA_FILE = __DIR__ . '/dashboard_data.json';
$DS_KEY    = 'YOUR_DEEPSEEK_API_KEY';

function load_data() {
    global $DATA_FILE;
    if (file_exists($DATA_FILE)) {
        $d = json_decode(file_get_contents($DATA_FILE), true) ?: [];
        // 兼容旧格式: 纯文本数组 → 新格式
        if (isset($d['todos']) && is_array($d['todos'])) {
            $fixed = [];
            foreach ($d['todos'] as $item) {
                if (is_string($item)) {
                    $fixed[] = ['t' => $item, 'd' => false];
                } elseif (is_array($item)) {
                    $fixed[] = $item;
                }
            }
            $d['todos'] = $fixed;
        }
        return $d;
    }
    return ['todos' => []];
}

function save_data($data) {
    global $DATA_FILE;
    file_put_contents($DATA_FILE, json_encode($data, JSON_UNESCAPED_UNICODE));
}

function get_balance() {
    global $DS_KEY;
    $ch = curl_init('https://api.deepseek.com/user/balance');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $DS_KEY,
            'Accept: application/json'
        ]
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($resp === false || $code !== 200) {
        return ['available' => 0, 'total' => 0, 'error' => 'API fail'];
    }
    $data = json_decode($resp, true);
    $infos = $data['balance_infos'] ?? [];
    $avail = 0; $total = 0;
    foreach ($infos as $info) {
        $avail += floatval($info['total_balance'] ?? 0);
        $total += floatval($info['topped_up_balance'] ?? 0);
    }
    return ['available' => $avail, 'total' => $total];
}

// ─── 路由 ───
$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

if ($method === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true) ?: [];
}

if ($action === 'all') {
    $data = load_data();
    $bal  = get_balance();
    // 只返回纯文本数组给Pico(兼容旧dashboard)
    $todos_raw = [];
    foreach (($data['todos'] ?? []) as $item) {
        $todos_raw[] = [
            't' => $item['t'] ?? '',
            'd' => $item['d'] ?? false
        ];
    }
    echo json_encode([
        'ds_balance' => $bal['available'] ?? 0,
        'ds_total'   => $bal['total'] ?? 0,
        'todos'      => $todos_raw,
        'error'      => $bal['error'] ?? null
    ], JSON_UNESCAPED_UNICODE);

} elseif ($action === 'todos' && $method === 'POST') {
    $data = load_data();
    $new = [];
    foreach (($body['todos'] ?? []) as $item) {
        if (is_string($item)) {
            $new[] = ['t' => $item, 'd' => false];
        } elseif (is_array($item)) {
            $new[] = $item;
        }
    }
    $data['todos'] = $new;
    save_data($data);
    echo json_encode(['ok' => true, 'count' => count($new)]);

} elseif ($action === 'done' && $method === 'POST') {
    $idx = intval($_GET['idx'] ?? -1);
    $data = load_data();
    if (isset($data['todos'][$idx])) {
        $data['todos'][$idx]['d'] = true;
        save_data($data);
        echo json_encode(['ok' => true]);
    } else {
        echo json_encode(['ok' => false, 'error' => 'bad index']);
    }

} elseif ($action === 'undone' && $method === 'POST') {
    $idx = intval($_GET['idx'] ?? -1);
    $data = load_data();
    if (isset($data['todos'][$idx])) {
        $data['todos'][$idx]['d'] = false;
        save_data($data);
        echo json_encode(['ok' => true]);
    } else {
        echo json_encode(['ok' => false, 'error' => 'bad index']);
    }

} elseif ($action === 'clear_done' && $method === 'POST') {
    $data = load_data();
    $data['todos'] = array_values(array_filter($data['todos'], fn($t) => !($t['d'] ?? false)));
    save_data($data);
    echo json_encode(['ok' => true, 'count' => count($data['todos'])]);

} else {
    http_response_code(404);
    echo json_encode(['error' => 'Unknown: ' . $action]);
}
