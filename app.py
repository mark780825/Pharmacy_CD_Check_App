import os
import datetime
import shutil
import pandas as pd
import html
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, redirect, url_for, flash, jsonify, render_template, session
from dotenv import load_dotenv

load_dotenv()
from jinja2 import DictLoader


import webbrowser
from threading import Timer

# ==========================================
# 1. 配置與靜態資料
# ==========================================
app = Flask(__name__)
app.secret_key = 'pharmacy_secure_key_123'
DB_NAME = 'pharmacy.db'

# 內建科別對照表
DEPARTMENTS_DATA = [
    ('00', '不分科'), ('01', '家醫科'), ('02', '內科'), ('03', '外科'), ('04', '兒科'),
    ('05', '婦產科'), ('06', '骨科'), ('07', '神經外科'), ('08', '泌尿科'), ('09', '耳鼻喉科'),
    ('10', '眼科'), ('11', '皮膚科'), ('12', '神經科'), ('13', '精神科'), ('14', '復健科'),
    ('15', '整形外科'), ('22', '急診醫學科'), ('23', '職業醫學科'), ('2A', '結核科'), ('2B', '洗腎科'),
    ('40', '牙科'), ('60', '中醫科'), ('81', '麻醉科'), ('82', '放射線科'), ('83', '病理科'),
    ('84', '核醫科'), ('AA', '消化內科'), ('AB', '心臟血管內科'), ('AC', '胸腔內科'), ('AD', '腎臟內科'),
    ('AE', '風濕免疫科'), ('AF', '血液腫瘤科'), ('AG', '內分泌科'), ('AH', '感染科'), ('AI', '潛醫科'),
    ('AJ', '胸腔暨重症加護'), ('AK', '老人醫學科'), ('BA', '直腸外科'), ('BB', '心臟血管外科'),
    ('BC', '胸腔外科'), ('BD', '消化外科'), ('CA', '小兒外科'), ('CB', '新生兒科'), ('DA', '疼痛科'),
    ('EA', '居家照護'), ('FA', '放射診斷科'), ('FB', '放射腫瘤科'), ('GA', '口腔顏面外科'),
    ('HA', '脊椎骨科'), ('TB', '肺結核')
]

# 嵌入式 HTML 模板
TEMPLATES = {
    'base': '''
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管藥提領確認系統</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { font-family: "Microsoft JhengHei", sans-serif; background-color: #f8f9fa; }
            .card { margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .status-badge { font-size: 0.8em; padding: 5px 10px; border-radius: 10px; }
            .status-pending { background-color: #ffeeba; color: #856404; }
            .status-done { background-color: #d4edda; color: #155724; }
            .header-bar { background-color: #007bff; color: white; padding: 10px; margin-bottom: 20px; }
            .warning-box { font-size: 0.85rem; padding: 5px; margin-top: 5px; border-radius: 4px; }
            .warn-reimb { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
            .warn-pack { background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; }
        </style>
    </head>
    <body>
        <div class="header-bar">
            <div class="container d-flex justify-content-between align-items-center">
                <h4 class="m-0">💊 管藥提領系統</h4>
                {% if session.get('user') %}
                    <div>
                        <span class="me-2">{{ session['user'] }}</span>
                        <a href="{{ url_for('logout') }}" class="btn btn-sm btn-outline-light">登出</a>
                    </div>
                {% endif %}
            </div>
        </div>
        <div class="container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            {% block content %}{% endblock %}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // [新增] 檢查 Bootstrap 是否載入成功 (防止因無網路導致按鈕沒反應)
            window.addEventListener('load', function() {
                if (typeof bootstrap === 'undefined') {
                    alert('⚠️ 警告：介面元件載入失敗！\\n\\n請確認您的平板/電腦已連上網際網路，\\n否則「提領」按鈕將無法運作。');
                }
            });

            // [新增] 防休眠機制 (Keep Alive)
            // 每 5 分鐘 (300000 ms) 發送一次請求，保持 Render 活躍
            setInterval(function() {
                fetch('/api/keep_alive')
                .then(res => console.log('Keep-alive ping success'))
                .catch(err => console.error('Keep-alive ping failed', err));
            }, 300000);
        </script>
    </body>
    </html>
    ''',
    
    'login': '''
    {% extends "base" %}
    {% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title text-center mb-4">藥師登入</h5>
                    <!-- <form method="POST" id="loginForm"> -->
                        <div class="d-grid gap-2">
                        {% for p_name in pharmacists %}
                            <button type="button" onclick="login('{{ p_name }}')" class="btn btn-outline-primary btn-lg">{{ p_name }}</button>
                        {% endfor %}
                        </div>
                    <!-- </form> -->
                    <script>
                    function login(name) {
                        let formData = new FormData();
                        formData.append('pharmacist_name', name);
                        formData.append('is_ajax', '1');

                        fetch('{{ url_for("login_post") }}', { 
                            method: 'POST', 
                            body: formData 
                        })
                        .then(res => res.json())
                        .then(data => {
                            if(data.import_msg) {
                                alert(data.import_msg);
                            }
                            window.location.href = data.redirect;
                        })
                        .catch(err => {
                            alert('登入錯誤: ' + err);
                        });
                    }
                    </script>
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header bg-success text-white">匯入處方資料 (DRUG.txt)</div>
                <div class="card-body">
                    <form action="{{ url_for('upload_prescription') }}" method="post" enctype="multipart/form-data">
                        <div class="input-group">
                            <input type="file" name="file" class="form-control" required>
                            <button class="btn btn-success" type="submit">上傳</button>
                        </div>
                        <div class="form-text">請選擇 HIS 匯出的文字檔</div>
                    </form>
                </div>
            </div>
            
            </div>


            <div class="text-center mt-3">
                <a href="{{ url_for('admin') }}" class="text-muted">後台管理</a>
            </div>
        </div>
    </div>

    <script>
    /*
    document.getElementById('btnImport').addEventListener('click', function() {
        let btn = this;
        btn.disabled = true;
        btn.innerHTML = '讀取中...';
        
        fetch('/api/import_now', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                alert(data.msg);
                location.reload();
            } else {
                alert('匯入失敗：' + data.msg);
                btn.disabled = false;
                btn.innerHTML = '📥 讀取處方 (預設路徑)';
            }
        }).catch(err => {
            alert('請求錯誤');
            btn.disabled = false;
            btn.innerHTML = '📥 讀取處方 (預設路徑)';
        });
    });
    */

    </script>
    {% endblock %}
    ''',

    'dashboard': '''
    {% extends "base" %}
    {% block content %}
    <h5 class="mb-3">待提領處方清單</h5>
    {% if prescriptions %}
        {% for p in prescriptions %}
        <a href="{{ url_for('prescription_detail', pid=p['id']) }}" class="text-decoration-none text-dark">
            <div class="card">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <h5 class="card-title mb-1">{{ p['patient_name'] }} <small class="text-muted">{{ p['patient_id'] }}</small></h5>
                        <div>
                            <span class="status-badge {{ 'status-done' if p['status'] == '已完成' else 'status-pending' }} me-2">
                                {{ p['status'] }}
                            </span>
                            <button class="btn btn-sm btn-outline-danger" onclick="deletePrescription(event, {{ p['id'] }})" style="z-index: 10;">🗑️ 刪除</button>
                        </div>
                    </div>
                    <p class="card-text mb-1 text-muted">
                        🏥 {{ p['institution_name'] }}<br>
                        🩺 {{ p['dept_name'] }} ({{ p['visit_date'] }})<br>
                        序號: {{ p['visit_seq'] }}<br>
                        領藥回數: {{ p['chronic_seq'] + '/' + p['chronic_total'] if p['chronic_seq'] and p['chronic_total'] else '1/1' }}
                    </p>
                    <div class="mt-2 text-danger">
                        <small>含管制藥品：{{ p['drug_names'] }}</small>
                    </div>
                </div>
            </div>
        </a>
        {% endfor %}
    {% else %}
        <div class="alert alert-info">目前沒有待處理的管制藥品處方。</div>
    {% endif %}
    
    <script>
    function deletePrescription(event, pid) {
        event.preventDefault(); // Prevent link navigation
        event.stopPropagation(); // Stop event bubbling
        
        if(!confirm('確定要刪除這張處方嗎？此動作無法復原。')) return;
        
        fetch('/api/delete_prescription/' + pid, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                location.reload();
            } else {
                alert('刪除失敗：' + data.msg);
            }
        });
    }
    </script>
    {% endblock %}
    ''',

    'detail': '''
    {% extends "base" %}
    {% block content %}
    <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary mb-3">&larr; 返回清單</a>
    
    <div class="card mb-4">
        <div class="card-header bg-light">處方資訊</div>
        <div class="card-body">
            <div class="row">
                <div class="col-6"><strong>患者姓名：</strong>{{ p['patient_name'] }}</div>
                <div class="col-6"><strong>身分證字號：</strong>{{ p['patient_id'] }}</div>
                <div class="col-12"><strong>醫院：</strong>{{ p['institution_name'] }}</div>
                <div class="col-6"><strong>科別：</strong>{{ p['dept_name'] }}</div>
                <div class="col-6"><strong>就醫日期：</strong>{{ p['visit_date'] }}</div>
                <div class="col-6"><strong>領藥回數：</strong>{{ p['chronic_seq'] + '/' + p['chronic_total'] if p['chronic_seq'] and p['chronic_total'] else '1/1' }}</div>
            </div>
        </div>
    </div>

    <h5 class="mb-3">管制藥品提領區</h5>
    {% for d in drugs %}
    <div class="card {{ 'border-success' if d['status'] == '已領' else 'border-danger' }}">
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h5 class="mb-0">
                        {{ d['ref_name'] }} 
                        <span class="badge bg-secondary ms-1">{{ d['product_code'] }}</span>
                    </h5>
                    
                    {% if d['warn_reimb'] %}
                        <div class="warning-box warn-reimb">
                            ⚠️ <strong>健保碼前兩碼不符</strong>：處方開立 {{ d['drug_code'] }}，庫存為 {{ d['ref_nh_code'] }}，請確認給付狀態
                        </div>
                    {% endif %}
                    {% if d['warn_pack'] %}
                        <div class="warning-box warn-pack">
                            📦 <strong>健保碼後三碼不符</strong>：處方開立 {{ d['drug_code'] }}，請確認應給散裝還是排裝藥
                        </div>
                    {% endif %}
                    {% if d['warn_no_barcode'] %}
                        <div class="small text-danger mt-1">※ 此藥品系統無條碼資料，請輸入商品代碼</div>
                    {% endif %}

                    <div class="text-muted mt-2">處方總量：<strong>{{ d['total_qty'] }}</strong></div>
                </div>
                
                {% if d['status'] == '已領' %}
                    <span class="badge bg-success">已完成 ({{ d['picked_qty'] }})</span>
                {% else %}
                    <button class="btn btn-danger" 
                            data-id="{{ d['id'] }}"
                            data-name="{{ d['ref_name_safe'] }}"
                            data-product="{{ d['product_code_safe'] }}"
                            data-barcode="{{ d['barcode_safe'] }}"
                            data-qty="{{ d['total_qty'] }}"
                            data-nh="{{ d['ref_nh_code'] if d.get('ref_nh_code') else d['drug_code'] }}"
                            onclick="openModal(this)">
                        提領
                    </button>
                {% endif %}
            </div>
            {% if d['status'] == '已領' %}
                <div class="small text-muted mt-2">提領人：{{ d['picked_by'] }} | 時間：{{ d['picked_at'] }}</div>
            {% endif %}
        </div>
    </div>
    {% endfor %}

    <div class="modal fade" id="pickModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">藥品核對</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="pickForm">
                        <input type="hidden" id="drug_id">
                        <input type="hidden" id="correct_product_code">
                        <input type="hidden" id="correct_barcode">
                        <input type="hidden" id="correct_qty">
                        <input type="hidden" id="target_nh_code">
                        
                        <h4 id="modalDrugName" class="text-primary text-center mb-3"></h4>
                        <h4 id="modalDrugName" class="text-primary text-center mb-3"></h4>
                        <div class="text-center text-muted mb-3">
                             請輸入代碼或掃描條碼
                        </div>

                        <div class="mb-3">
                            <label class="form-label">1. 掃描條碼 或 輸入商品代碼</label>
                            <input type="text" class="form-control form-control-lg" id="input_code" autocomplete="off" placeholder="掃描或手輸" style="ime-mode: disabled;">
                            <div id="code_error" class="text-danger small mt-1" style="display:none;">❌ 核對失敗！代碼或條碼不符。</div>
                        </div>

                        <div class="mb-3" id="qty_group" style="opacity: 0.5; pointer-events: none;">
                            <label class="form-label">2. 確認提領數量 (處方量: <span id="display_qty"></span>)</label>
                            <input type="number" class="form-control form-control-lg" id="input_qty" placeholder="輸入數量">
                            <div id="qty_error" class="text-danger small mt-1" style="display:none;">❌ 數量與處方不符！</div>
                        </div>

                        <!-- Numeric Keypad -->
                        <div id="numpad" class="mt-3">
                            <style>
                                .numpad-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
                                .numpad-btn { height: 60px; font-size: 1.5rem; font-weight: bold; }
                            </style>
                            <div class="numpad-grid">
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(1)">1</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(2)">2</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(3)">3</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(4)">4</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(5)">5</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(6)">6</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(7)">7</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(8)">8</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(9)">9</button>
                                <button type="button" class="btn btn-warning numpad-btn" onclick="pad('C')">C</button>
                                <button type="button" class="btn btn-light numpad-btn" onclick="pad(0)">0</button>
                                <button type="button" class="btn btn-primary numpad-btn" onclick="pad('Enter')">Go</button>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" id="btnConfirm" disabled>確認提領</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        var pickModal = null;
        var currentInput = null; // Track focused input
        
        // 確保 Bootstrap 載入後再初始化 Modal
        window.addEventListener('load', function() {
            if (typeof bootstrap !== 'undefined') {
                pickModal = new bootstrap.Modal(document.getElementById('pickModal'));
            }
        });

        function openModal(btn) {
            if (!pickModal) {
                alert('介面載入失敗 (Bootstrap未載入)。請檢查網路連線。');
                return;
            }

            var id = btn.getAttribute('data-id');
            var name = btn.getAttribute('data-name');
            var product_code = btn.getAttribute('data-product');
            var barcode = btn.getAttribute('data-barcode');
            var qty = btn.getAttribute('data-qty');
            var nh_code = btn.getAttribute('data-nh');
            
            document.getElementById('drug_id').value = id;
            document.getElementById('correct_product_code').value = product_code;
            document.getElementById('correct_barcode').value = barcode;
            document.getElementById('correct_qty').value = qty;
            document.getElementById('target_nh_code').value = nh_code;
            
            document.getElementById('modalDrugName').innerText = name;
            // document.getElementById('modalProductCodeDisplay').innerText = product_code; // Hidden
            document.getElementById('display_qty').innerText = qty;
            
            // 重置表單
            document.getElementById('input_code').value = '';
            document.getElementById('input_qty').value = '';
            document.getElementById('code_error').style.display = 'none';
            document.getElementById('qty_error').style.display = 'none';
            document.getElementById('qty_group').style.opacity = '0.5';
            document.getElementById('qty_group').style.pointerEvents = 'none';
            document.getElementById('btnConfirm').disabled = true;
            
            pickModal.show();
            setTimeout(() => {
                document.getElementById('input_code').focus();
                currentInput = document.getElementById('input_code');
            }, 500);
        }
        
        // Focus tracking
        document.getElementById('input_code').addEventListener('focus', function() { currentInput = this; });
        document.getElementById('input_qty').addEventListener('focus', function() { currentInput = this; });

        // Keypad Logic
        function pad(val) {
            if (!currentInput) return;
            
            if (val === 'C') {
                currentInput.value = '';
            } else if (val === 'Enter') {
                if (currentInput.id === 'input_code') checkCode();
                if (currentInput.id === 'input_qty') checkQty();
            } else {
                currentInput.value += val;
            }
        }

        // document.getElementById('input_code').addEventListener('change', checkCode); // Removed auto-check
        document.getElementById('input_code').addEventListener('keyup', function(e) {
            if(e.key === 'Enter') checkCode();
        });

        // [新增] 自動將全形字轉半形 (解決中文輸入法問題)
        document.getElementById('input_code').addEventListener('input', function() {
            let val = this.value;
            let tmp = "";
            for(let i=0; i<val.length; i++){
                let c = val.charCodeAt(i);
                // 0-9 (Fullwidth 0xFF10 - 0xFF19) -> (0x30 - 0x39)
                if(c >= 0xFF10 && c <= 0xFF19) tmp += String.fromCharCode(c - 0xFEE0);
                // A-Z (Fullwidth)
                else if(c >= 0xFF21 && c <= 0xFF3A) tmp += String.fromCharCode(c - 0xFEE0);
                // a-z (Fullwidth)
                else if(c >= 0xFF41 && c <= 0xFF5A) tmp += String.fromCharCode(c - 0xFEE0);
                else tmp += val.charAt(i);
            }
            if(tmp !== val) this.value = tmp;
        });

        function checkCode() {
            let input = document.getElementById('input_code').value.trim();
            if (input === '') return;

            let correctProd = document.getElementById('correct_product_code').value.trim();
            let correctBar = document.getElementById('correct_barcode').value.trim();
            
            let isMatch = false;
            let cleanInput = input.replace(/^0+/, '');
            let cleanProd = correctProd.replace(/^0+/, '');
            
            if (cleanInput === cleanProd && cleanInput !== '') {
                isMatch = true;
            }
            if (correctBar && correctBar !== 'None' && input === correctBar) {
                isMatch = true;
            }

            if (isMatch) {
                document.getElementById('code_error').style.display = 'none';
                document.getElementById('input_code').classList.add('is-valid');
                document.getElementById('qty_group').style.opacity = '1';
                document.getElementById('qty_group').style.pointerEvents = 'auto';
                
                // Delay focus to ensure keypad doesn't accidentally trigger something else
                setTimeout(() => {
                    document.getElementById('input_qty').focus();
                    currentInput = document.getElementById('input_qty');
                }, 100);
            } else {
                document.getElementById('code_error').style.display = 'block';
                document.getElementById('input_code').classList.remove('is-valid');
                document.getElementById('input_code').value = ''; 
                document.getElementById('input_code').focus(); // Refocus
            }
        }
        
        document.getElementById('input_qty').addEventListener('keyup', function(e) {
            if(e.key === 'Enter') checkQty();
        });

        function checkQty() {
            let val = document.getElementById('input_qty').value;
            if(!val) return;
            
            let qty = parseFloat(val);
            let correct = parseFloat(document.getElementById('correct_qty').value);
            let btn = document.getElementById('btnConfirm');
            
            if (qty === correct) {
                document.getElementById('qty_error').style.display = 'none';
                document.getElementById('input_qty').classList.add('is-valid');
                btn.disabled = false;
            } else {
                document.getElementById('qty_error').style.display = 'block';
                document.getElementById('input_qty').classList.remove('is-valid');
                btn.disabled = true;
            }
        }

        document.getElementById('btnConfirm').addEventListener('click', function() {
            let drug_id = document.getElementById('drug_id').value;
            let qty = document.getElementById('input_qty').value;
            let code = document.getElementById('target_nh_code').value;
            
            fetch('/api/pick_drug', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({drug_id: drug_id, qty: qty, code: code})
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    if (data.completed) {
                        if (data.system_has_pending) {
                            alert('本張處方提領完畢！將跳轉至待提領清單。');
                            window.location.href = "{{ url_for('dashboard') }}";
                        } else {
                            alert('所有處方皆已完成！系統將自動登出。');
                            window.location.href = "{{ url_for('logout') }}";
                        }
                    } else {
                        location.reload();
                    }
                } else {
                    alert('錯誤：' + data.msg);
                }
            });
        });
    </script>
    {% endblock %}
    ''',

    'history': '''
    {% extends "base" %}
    {% block content %}
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h4>📜 歷史提領紀錄查詢</h4>
            <a href="{{ url_for('login') }}" class="btn btn-secondary">返回登入</a>
        </div>
        
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" action="{{ url_for('history') }}" class="row g-3">
                    <div class="col-md-3">
                        <label class="form-label">開始日期</label>
                        <input type="date" class="form-control" name="start_date" value="{{ start_date }}">
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">結束日期</label>
                        <input type="date" class="form-control" name="end_date" value="{{ end_date }}">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">查詢方式</label>
                        <select class="form-select" name="q_type">
                            <option value="patient" {{ 'selected' if q_type == 'patient' }}>身分證字號</option>
                            <option value="drug" {{ 'selected' if q_type == 'drug' }}>藥品(代碼/條碼)</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">關鍵字</label>
                        <input type="text" class="form-control" name="q_val" value="{{ q_val }}" placeholder="請輸入...">
                    </div>
                    <div class="col-md-1 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary w-100">查詢</button>
                    </div>
                </form>
            </div>
        </div>

        {% if results is not none %}
        <div class="card">
            <div class="card-body">
                <h6 class="card-title text-muted mb-3">查詢結果 (共 {{ results|length }} 筆處方)</h6>
                <div class="table-responsive">
                    <table class="table table-bordered table-hover align-middle">
                        <thead class="table-light">
                            <tr>
                                <th width="35%">處方與就醫資訊</th>
                                <th width="65%">藥品提領明細</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for group in results %}
                            {% set meta = group.meta %}
                            <tr>
                                <td>
                                    <h5 class="mb-1">{{ meta['patient_name'] }} <small class="text-muted">{{ meta['patient_id'] }}</small></h5>
                                    <div class="small text-muted mb-2">
                                        🏥 {{ meta['inst_name'] or meta['institution_code'] }}<br>
                                        🩺 {{ meta['dept_name'] or meta['dept_code'] }}<br>
                                        <br>領藥回數: {{ meta['chronic_seq'] + '/' + meta['chronic_total'] if meta['chronic_seq'] else '1/1' }}
                                    </div>
                                    <div class="mt-2">
                                        <button class="btn btn-sm btn-outline-primary" onclick='editHistory({{ group|tojson }})'>✏️ 修改</button>
                                        <button class="btn btn-sm btn-outline-danger" onclick="deleteHistory({{ meta['p_id'] }})">🗑️ 刪除</button>
                                    </div>
                                </td>
                                <td class="p-0">
                                    <table class="table table-sm table-borderless mb-0">
                                        <tbody>
                                            {% for d in group['drugs'] %}
                                            <tr class="border-bottom">
                                                <td class="ps-3 pt-2 pb-2">
                                                    <strong>{{ d['drug_name'] or d['drug_code'] }}</strong>
                                                    <br><small class="text-muted">代碼: {{ d['drug_code'] }}</small>
                                                    
                                                    {% if d['drug_status'] == '已領' %}
                                                        <span class="badge bg-success ms-2">領: {{ d['picked_qty'] }}</span>
                                                    {% else %}
                                                        <span class="badge bg-danger ms-2">未提領</span>
                                                        <br><small class="text-muted">處方量: {{ d['total_qty'] if d.get('total_qty') else '-' }}</small>
                                                    {% endif %}
                                                </td>
                                                <td class="text-end pe-3 pt-2 pb-2">
                                                    {% if d['drug_status'] == '已領' %}
                                                        <small>{{ d['picked_at'] }}</small><br>
                                                        <strong>{{ d['picked_by'] }}</strong>
                                                        {% if d['modified_by'] %}
                                                        <br><small class="text-muted">修: {{ d['modified_by'] }} ({{ d['modified_at'] }})</small>
                                                        {% endif %}
                                                    {% else %}
                                                        <small class="text-muted">-</small>
                                                    {% endif %}
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="2" class="text-center text-muted py-4">在此期間查無相符資料</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <!-- Edit Modal -->
    <div class="modal fade" id="editHistoryModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">修改提領資料</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="editHistoryForm">
                        <input type="hidden" id="edit_pd_id">
                        
                        <h6 class="text-primary mb-3">處方詳細資料</h6>
                        <div class="row g-2 mb-2">
                            <div class="col-md-6">
                                <label class="form-label">患者姓名</label>
                                <input type="text" class="form-control" id="edit_p_name">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">身分證字號</label>
                                <input type="text" class="form-control" id="edit_p_id">
                            </div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-md-6">
                                <label class="form-label">就醫日期</label>
                                <input type="text" class="form-control" id="edit_visit_date">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">就醫序號</label>
                                <input type="text" class="form-control" id="edit_visit_seq">
                            </div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-md-6">
                                <label class="form-label">院所代碼</label>
                                <input type="text" class="form-control" id="edit_inst_code">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">科別代碼</label>
                                <input type="text" class="form-control" id="edit_dept_code">
                            </div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-md-6">
                                <label class="form-label">慢性病調劑序號</label>
                                <input type="text" class="form-control" id="edit_c_seq">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">慢性病總次數</label>
                                <input type="text" class="form-control" id="edit_c_total">
                            </div>
                        </div>

                        <hr>
                        <h6 class="text-primary mb-3">提領/修改資訊</h6>
                        <div class="mb-3">
                            <label class="form-label">修改人員</label>
                            <select class="form-select" id="edit_modifier" required>
                                {% for p in pharmacists %}
                                <option value="{{ p }}">{{ p }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div id="edit_drugs_container">
                            <!-- Dynamic Drug Inputs -->
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="button" class="btn btn-primary" onclick="saveHistoryEdit()">儲存修改</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    function deleteHistory(p_id) {
        if(!confirm('確定要刪除整筆處方的提領紀錄嗎？')) return;
        
        fetch('/api/history/delete_group', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({p_id: p_id})
        }).then(res => res.json()).then(data => {
            if(data.success) {
                location.reload();
            } else {
                alert('刪除失敗：' + data.msg);
            }
        });
    }

    var editModal = null;
    function editHistory(group) {
        if (!editModal) if(typeof bootstrap !== 'undefined') editModal = new bootstrap.Modal(document.getElementById('editHistoryModal'));
        if(editModal) {
            let meta = group.meta;
            document.getElementById('edit_pd_id').value = meta.p_id; // Using field to store p_id
            
            // Prescriptions data
            document.getElementById('edit_p_name').value = meta.patient_name;
            document.getElementById('edit_p_id').value = meta.patient_id;
            document.getElementById('edit_visit_date').value = meta.visit_date;
            document.getElementById('edit_visit_seq').value = meta.visit_seq;
            document.getElementById('edit_inst_code').value = meta.institution_code;
            document.getElementById('edit_dept_code').value = meta.dept_code;
            document.getElementById('edit_c_seq').value = meta.chronic_seq;
            document.getElementById('edit_c_total').value = meta.chronic_total;
            
            // Drugs Generation
            let container = document.getElementById('edit_drugs_container');
            container.innerHTML = '';
            group.drugs.forEach((d, idx) => {
                let html = `
                    <div class="card bg-light mb-2 drug-row">
                        <div class="card-body p-2">
                            <input type="hidden" class="drug-pd-id" value="${d.pd_id}">
                            <div class="row g-2 align-items-center">
                                <div class="col-md-5">
                                    <label class="form-label small mb-0">藥品代碼</label>
                                    <input type="text" class="form-control form-control-sm drug-code" value="${d.drug_code}">
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label small mb-0">提領數量</label>
                                    <input type="number" step="0.01" class="form-control form-control-sm drug-qty" value="${d.picked_qty}">
                                </div>
                                <div class="col-md-4">
                                     <small class="text-muted d-block text-truncate" title="${d.drug_name}">${d.drug_name || '-'}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', html);
            });

            editModal.show();
        } else {
             alert('UI Error: Bootstrap not loaded');
        }
    }

    function saveHistoryEdit() {
        let p_id = document.getElementById('edit_pd_id').value; // Stores p_id
        let modifier = document.getElementById('edit_modifier').value;
        
        let drugs = [];
        document.querySelectorAll('.drug-row').forEach(row => {
            drugs.push({
                pd_id: row.querySelector('.drug-pd-id').value,
                code: row.querySelector('.drug-code').value,
                qty: row.querySelector('.drug-qty').value
            });
        });

        let data = {
            p_id: p_id,
            modifier: modifier,
            drugs: drugs,
            // Prescription fields
            p_name: document.getElementById('edit_p_name').value,
            p_id_val: document.getElementById('edit_p_id').value,
            visit_date: document.getElementById('edit_visit_date').value,
            visit_seq: document.getElementById('edit_visit_seq').value,
            inst_code: document.getElementById('edit_inst_code').value,
            dept_code: document.getElementById('edit_dept_code').value,
            c_seq: document.getElementById('edit_c_seq').value,
            c_total: document.getElementById('edit_c_total').value
        };

        fetch('/api/history/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        }).then(res => res.json()).then(resp => {
            if(resp.success) {
                location.reload();
            } else {
                alert('修改失敗：' + resp.msg);
            }
        });
    }
    </script>
    {% endblock %}
    ''',

    'admin': '''
    {% extends "base" %}
    {% block content %}
    <div class="row">
        <div class="col-md-6">
            <div class="card mb-4">
                <div class="card-header bg-secondary text-white">人員設定</div>
                <div class="card-body">
                    <form action="{{ url_for('admin_settings') }}" method="post">
                        <div class="mb-3">
                            <label class="form-label">人員名單 (以逗號分隔)</label>
                            <textarea name="pharmacists" class="form-control" rows="3" placeholder="例如：藥師A,藥師B,王大明">{{ settings_pharmacists or '' }}</textarea>
                        </div>
                        <button class="btn btn-secondary w-100" type="submit">更新人員設定</button>
                    </form>
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-warning text-dark">資料匯入與更新</div>
                <div class="card-body">
                    <form action="{{ url_for('upload_controlled_list') }}" method="post" enctype="multipart/form-data" class="mb-4">
                        <label class="form-label">1. 更新管制藥品清單 CSV</label>
                        <div class="input-group">
                            <input type="file" name="file" class="form-control" required>
                            <button class="btn btn-secondary" type="submit">更新清單</button>
                        </div>
                        <div class="form-text">CSV欄位：健保碼, 內部參照, 名稱, 條碼</div>
                    </form>
                    
                    <hr>
                    
                    <form action="{{ url_for('upload_institutions') }}" method="post" enctype="multipart/form-data">
                        <label class="form-label">2. 更新醫療機構名冊 CSV</label>
                        <div class="input-group">
                            <input type="file" name="file" class="form-control" required>
                            <button class="btn btn-secondary" type="submit">更新機構</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">系統狀態</div>
                <div class="card-body">
                    <ul>
                        <li>資料庫來源：雲端資料庫 (Supabase)</li>
                        <li>醫療機構資料：{{ stats['institutions'] }} 筆</li>
                        <li>內建科別資料：{{ stats['departments'] }} 筆 (已載入)</li>
                        <li>管制藥品品項：{{ stats['controlled_drugs'] }} 筆</li>
                        <li>目前待提領處方：{{ stats['pending_prescriptions'] }} 張</li>
                    </ul>
                    <a href="{{ url_for('login') }}" class="btn btn-outline-primary">回登入頁</a>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    ''',

    'login': '''
    {% extends "base" %}
    {% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title text-center mb-4">藥師登入</h5>
                    <!-- <form method="POST" id="loginForm"> -->
                        <div class="d-grid gap-2">
                        {% for p_name in pharmacists %}
                            <button type="button" onclick="login('{{ p_name }}')" class="btn btn-outline-primary btn-lg">{{ p_name }}</button>
                        {% endfor %}
                        </div>
                    <!-- </form> -->
                    <script>
                    function login(name) {
                        let formData = new FormData();
                        formData.append('pharmacist_name', name);
                        formData.append('is_ajax', '1');

                        fetch('{{ url_for("login_post") }}', { 
                            method: 'POST', 
                            body: formData 
                        })
                        .then(res => res.json())
                        .then(data => {
                            if(data.import_msg) {
                                alert(data.import_msg);
                            }
                            window.location.href = data.redirect;
                        })
                        .catch(err => {
                            alert('登入錯誤: ' + err);
                        });
                    }
                    </script>
                </div>
            </div>
            
            <div class="d-grid mt-3 gap-2">
                 <button class="btn btn-outline-warning" id="btnTransfer">🚚 轉移匯出檔</button>

                 <a href="{{ url_for('history') }}" class="btn btn-outline-info">📜 查詢提領紀錄</a>
            </div>

            <div class="text-center mt-3">
                <a href="{{ url_for('admin') }}" class="text-muted">後台管理</a>
            </div>
        </div>
    </div>

    <script>


    // [新增] 轉移檔案功能
    document.getElementById('btnTransfer').addEventListener('click', function() {
        let btn = this;
        if(!confirm('即將執行：\\n從「來源資料夾」移動 DRUG.txt 到「目標資料夾」\\n(若目標已有檔案將被覆蓋)\\n\\n確定要執行嗎？')) return;

        btn.disabled = true;
        btn.innerHTML = '轉移中...';
        
        fetch('/api/transfer_file', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                alert('✅ 成功：' + data.msg);
            } else {
                alert('❌ 失敗：' + data.msg);
            }
            btn.disabled = false;
            btn.innerHTML = '🚚 轉移匯出檔';
        }).catch(err => {
            alert('請求錯誤：' + err);
            btn.disabled = false;
            btn.innerHTML = '🚚 轉移匯出檔';
        });
    });
    </script>
    {% endblock %}
    '''
}

app.jinja_loader = DictLoader(TEMPLATES)

# ==========================================
# 3. 資料庫操作
# ==========================================
# ==========================================
# 3. 資料庫操作
# ==========================================

# 3. 資料庫操作
# ==========================================
def get_db():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'), cursor_factory=RealDictCursor)
    return conn

def get_setting(key):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('SELECT value FROM settings WHERE key = %s', (key,))
        row = cur.fetchone()
        conn.close()
        return row['value'] if row else None
    except Exception as e:
        print(f"Error getting setting {key}: {e}")
        return None

def update_setting(key, value):
    conn = get_db()
    try:
        cur = conn.cursor()
        # Postgres UPSERT
        cur.execute('''
            INSERT INTO settings (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        ''', (key, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating setting {key}: {e}")

# init_db removed as it is handled by migration script



# ==========================================
# 5. Flask 路由
# ==========================================
@app.route('/api/delete_prescription/<int:pid>', methods=['POST'])
def delete_prescription_api(pid):
    if not session.get('user'): return jsonify({'success': False, 'msg': 'Unauthorized'}), 401
    try:
        conn = get_db()
        cur = conn.cursor()
        # Delete related drugs first
        cur.execute('DELETE FROM prescription_drugs WHERE prescription_id = %s', (pid,))
        # Delete prescription
        cur.execute('DELETE FROM prescriptions WHERE id = %s', (pid,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'msg': '已刪除'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

# ==========================================
# 4. 處方解析
# ==========================================
def parse_and_import_prescription(file_path):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT nh_code FROM controlled_drugs")
    controlled_nh_codes = [row['nh_code'] for row in cursor.fetchall()]
    controlled_middle_5_set = set()
    for c in controlled_nh_codes:
        if len(c) >= 7: controlled_middle_5_set.add(c[2:7])
        else: controlled_middle_5_set.add(c)
    
    with open(file_path, 'r', encoding='cp950', errors='ignore') as f: lines = f.readlines()
    imported_count = 0
    skipped_reasons = []
    groups = []
    current_group = {'header': None, 'drugs': []}
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('^'):
            if current_group['header']: groups.append(current_group)
            current_group = {'header': line, 'drugs': []}
        else:
            if current_group['header']: current_group['drugs'].append(line)
    if current_group['header']: groups.append(current_group)
        
    for group in groups:
        has_controlled = False
        valid_drugs = []
        for drug_line in group['drugs']:
            parts = drug_line.split(',')
            if len(parts) > 0:
                drug_code = parts[0].strip()
                is_match = False
                if len(drug_code) >= 7:
                    mid5 = drug_code[2:7]
                    if mid5 in controlled_middle_5_set: is_match = True
                elif drug_code in controlled_nh_codes: is_match = True
                if is_match:
                    has_controlled = True
                    try: total_qty = float(parts[5])
                    except: total_qty = 0
                    valid_drugs.append({'code': drug_code, 'qty': total_qty})
        if has_controlled:
            header_parts = group['header'].split(',')
            try:
                p_data = {
                    'patient_id': header_parts[0].replace('^', ''),
                    'patient_name': header_parts[2],
                    'institution_code': header_parts[3],
                    'dept_code': header_parts[10], 
                    'visit_date': header_parts[11],
                    'visit_seq': header_parts[14] if len(header_parts) > 14 else '',
                    'chronic_seq': header_parts[16] if len(header_parts) > 16 else '',
                    'chronic_total': header_parts[17] if len(header_parts) > 17 else ''
                }
                if not p_data['patient_id']: continue

                # Check for existing prescription
                cursor.execute('''SELECT id, status FROM prescriptions 
                                  WHERE patient_id=%(patient_id)s 
                                  AND visit_date=%(visit_date)s 
                                  AND visit_seq=%(visit_seq)s 
                                  AND institution_code=%(institution_code)s
                                  AND dept_code=%(dept_code)s
                                  AND chronic_seq=%(chronic_seq)s''', p_data)
                existing = cursor.fetchone()
                
                if existing:
                    if existing['status'] == '已完成':
                        skipped_reasons.append(f"{p_data['patient_name']} ({p_data['visit_date']} 序號{p_data['visit_seq']}): 已完成提領")
                        continue
                    else:
                        # If exists but not completed, delete old one to update content
                        cursor.execute('DELETE FROM prescription_drugs WHERE prescription_id=%s', (existing['id'],))
                        cursor.execute('DELETE FROM prescriptions WHERE id=%s', (existing['id'],))
                
                cursor.execute('''INSERT INTO prescriptions (patient_name, patient_id, visit_date, visit_seq, institution_code, dept_code, chronic_seq, chronic_total) VALUES (%(patient_name)s, %(patient_id)s, %(visit_date)s, %(visit_seq)s, %(institution_code)s, %(dept_code)s, %(chronic_seq)s, %(chronic_total)s) RETURNING id''', p_data)
                p_id = cursor.fetchone()['id']
                for d in valid_drugs:
                    cursor.execute('''INSERT INTO prescription_drugs (prescription_id, drug_code, total_qty) VALUES (%s, %s, %s)''', (p_id, d['code'], d['qty']))
                imported_count += 1
            except Exception as e:
                print(f"Error parsing group: {e}")
                pass
    conn.commit()
    conn.close()
    return imported_count, skipped_reasons

# ==========================================
# 5. Flask 路由
# ==========================================
@app.route('/')
def login():
    p_str = get_setting('pharmacists')
    if p_str:
        pharmacists = [x.strip() for x in p_str.split(',') if x.strip()]
    else:
        pharmacists = ['藥師A', '藥師B', '藥師C'] # Default fallback
    return render_template('login', pharmacists=pharmacists)

@app.route('/', methods=['POST'])
@app.route('/', methods=['POST'])
def login_post():
    # [移除] 雲端版不再支援自動讀取本地檔案
    import_msg = None

    session['user'] = request.form.get('pharmacist_name')
    
    if request.form.get('is_ajax') == '1':
        return jsonify({
            'success': True,
            'redirect': url_for('dashboard'),
            'import_msg': import_msg
        })
    else:
        # Fallback for non-JS (though we disabled form) or if flash is preferred
        if import_msg: flash(import_msg, 'info')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('user'): return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    query = '''SELECT p.*, m.name as institution_name, d.name as dept_name FROM prescriptions p LEFT JOIN medical_institutions m ON p.institution_code = m.code LEFT JOIN departments d ON p.dept_code = d.code WHERE p.status != '已完成' ORDER BY p.created_at DESC'''
    cur.execute(query)
    prescriptions = [dict(row) for row in cur.fetchall()]
    for p in prescriptions:
        cur.execute('SELECT drug_code FROM prescription_drugs WHERE prescription_id = %s', (p['id'],))
        d_codes = [r['drug_code'] for r in cur.fetchall()]
        p['drug_names'] = ', '.join(d_codes)
    conn.close()
    return render_template('dashboard', prescriptions=prescriptions)

@app.route('/prescription/<int:pid>')
def prescription_detail(pid):
    if not session.get('user'): return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''SELECT p.*, m.name as institution_name, d.name as dept_name FROM prescriptions p LEFT JOIN medical_institutions m ON p.institution_code = m.code LEFT JOIN departments d ON p.dept_code = d.code WHERE p.id = %s''', (pid,))
    p = cur.fetchone()
    cur.execute('SELECT * FROM prescription_drugs WHERE prescription_id = %s', (pid,))
    p_drugs = cur.fetchall()
    cur.execute('SELECT nh_code, product_code, name, barcode FROM controlled_drugs')
    c_drugs = cur.fetchall()
    ref_map = {}
    for cd in c_drugs:
        code = cd['nh_code']
        if len(code) >= 7:
            mid5 = code[2:7]
            if mid5 not in ref_map: ref_map[mid5] = {'nh_code': cd['nh_code'], 'product_code': cd['product_code'], 'barcode': cd['barcode'], 'name': cd['name']}
    drugs_display = []
    for pd in p_drugs:
        d_dict = dict(pd)
        p_code = d_dict['drug_code']
        d_dict['ref_name'] = p_code; d_dict['product_code'] = '?'; d_dict['barcode'] = ''; d_dict['warn_reimb'] = False; d_dict['warn_pack'] = False; d_dict['warn_no_barcode'] = False
        
        if len(p_code) >= 7:
            p_mid5 = p_code[2:7]
            if p_mid5 in ref_map:
                ref = ref_map[p_mid5]; ref_nh_code = ref['nh_code']
                d_dict['ref_name'] = ref['name']; d_dict['ref_nh_code'] = ref_nh_code; d_dict['product_code'] = ref['product_code']; d_dict['barcode'] = ref['barcode'] if ref['barcode'] else ''
                if not d_dict['barcode']: d_dict['warn_no_barcode'] = True
                if p_code[:2] != ref_nh_code[:2]: d_dict['warn_reimb'] = True
                if p_code[7:] != ref_nh_code[7:]: d_dict['warn_pack'] = True
        
        # [修正] 增加安全轉義欄位 (Safe Fields) 以處理藥名中的引號
        d_dict['ref_name_safe'] = html.escape(str(d_dict['ref_name']))
        d_dict['product_code_safe'] = html.escape(str(d_dict['product_code']))
        d_dict['barcode_safe'] = html.escape(str(d_dict['barcode']))
        
        drugs_display.append(d_dict)
    conn.close()
    return render_template('detail', p=p, drugs=drugs_display)

@app.route('/api/pick_drug', methods=['POST'])
def pick_drug():
    if not session.get('user'): return jsonify({'success': False, 'msg': '請先登入'})
    data = request.json
    drug_id = data.get('drug_id'); qty = data.get('qty'); code = data.get('code')
    conn = get_db()
    cur = conn.cursor()
    
    # Update status AND drug_code (to actual picked item code)
    cur.execute("UPDATE prescription_drugs SET picked_qty = %s, drug_code = %s, picked_by = %s, picked_at = %s, status = '已領' WHERE id = %s", (qty, code, session['user'], datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), drug_id))
    
    cur.execute('SELECT prescription_id FROM prescription_drugs WHERE id = %s', (drug_id,))
    row = cur.fetchone()
    
    completed = False
    system_has_pending = True
    
    if row:
        pid = row['prescription_id']
        cur.execute("SELECT count(*) as cnt FROM prescription_drugs WHERE prescription_id = %s AND status = '未領'", (pid,))
        remaining = cur.fetchone()['cnt']
        if remaining == 0: 
            completed = True
            cur.execute("UPDATE prescriptions SET status = '已完成' WHERE id = %s", (pid,))
            
            # Check if any OTHER prescriptions are pending
            cur.execute("SELECT count(*) as cnt FROM prescriptions WHERE status != '已完成'")
            total_pending = cur.fetchone()['cnt']
            if total_pending == 0: system_has_pending = False
            
    conn.commit(); conn.close()
    return jsonify({'success': True, 'completed': completed, 'system_has_pending': system_has_pending})

@app.route('/admin')
def admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT count(*) as cnt FROM medical_institutions')
    inst_count = cur.fetchone()['cnt']
    cur.execute('SELECT count(*) as cnt FROM departments')
    dept_count = cur.fetchone()['cnt']
    cur.execute('SELECT count(*) as cnt FROM controlled_drugs')
    drug_count = cur.fetchone()['cnt']
    cur.execute("SELECT count(*) as cnt FROM prescriptions WHERE status != '已完成'")
    pending_count = cur.fetchone()['cnt']

    stats = {
        'institutions': inst_count,
        'departments': dept_count,
        'controlled_drugs': drug_count,
        'pending_prescriptions': pending_count
    }
    settings_pharmacists = get_setting('pharmacists')
    
    conn.close()
    return render_template('admin', stats=stats, settings_pharmacists=settings_pharmacists)

@app.route('/upload_prescription', methods=['POST'])
def upload_prescription():
    if 'file' not in request.files: return 'No file'
    f = request.files['file']
    path = os.path.join('uploads', f.filename)
    if not os.path.exists('uploads'): os.makedirs('uploads')
    f.save(path)
    count = parse_and_import_prescription(path)
    flash(f'成功匯入 {count} 張含管藥處方', 'success')
    return redirect(url_for('login'))

@app.route('/upload_controlled_list', methods=['POST'])
def upload_controlled_list():
    if 'file' not in request.files: return 'No file'
    f = request.files['file']
    try:
        try: df = pd.read_csv(f, encoding='utf-8-sig')
        except:
            f.seek(0)
            try: df = pd.read_csv(f, encoding='cp950')
            except:
                f.seek(0); df = pd.read_csv(f, encoding='ansi')
        df.columns = [str(c).strip() for c in df.columns]
        data = []
        
        # Check if we have standard headers
        has_headers = '健保碼' in df.columns and '名稱' in df.columns
        
        for _, row in df.iterrows():
            try:
                if has_headers:
                    nh = str(row['健保碼']).strip(); name = str(row['名稱']).strip()
                    try: prod = str(int(float(row['內部參照']))).strip()
                    except: prod = str(row['內部參照']).strip() if '內部參照' in df.columns else ''
                    
                    bc = None
                    if '條碼' in df.columns:
                        try: 
                            raw_bc = row['條碼']
                            if pd.notna(raw_bc) and str(raw_bc).strip() != '': bc = str(int(float(raw_bc))).strip()
                        except: bc = str(row['條碼']).strip()
                else:
                    # Fallback to positional (0:NH, 1:Prod, 2:Name, 3:Barcode)
                    if len(row) < 3: continue
                    nh = str(row.iloc[0]).strip()
                    prod = str(row.iloc[1]).strip()
                    name = str(row.iloc[2]).strip()
                    bc = None
                    if len(row) > 3:
                         try: 
                            raw_bc = row.iloc[3]
                            if pd.notna(raw_bc) and str(raw_bc).strip() != '': bc = str(int(float(raw_bc))).strip()
                         except: bc = str(row.iloc[3]).strip()
                
                # Basic validation
                if len(nh) < 5 or name == '': continue
                
                # Cleanup .0 from float conversion of codes if happens
                if prod.endswith('.0'): prod = prod[:-2]
                
                data.append((nh, prod, name, bc, '4'))
            except: continue
        
        if not data:
            flash('錯誤：找不到有效資料。請確認 CSV 包含正確標題 (健保碼, 內部參照, 名稱, 條碼) 或至少有正確的欄位順序。', 'danger')
            return redirect(url_for('admin'))
        conn = get_db()
        cur = conn.cursor()
        
        # [修改] 使用者要求「全覆蓋」而非合併，因此先清空資料表
        cur.execute("DELETE FROM controlled_drugs")
        
        cur.executemany('''
            INSERT INTO controlled_drugs (nh_code, product_code, name, barcode, level) 
            VALUES (%s, %s, %s, %s, %s)
        ''', data)
        conn.commit(); conn.close()
        flash(f'成功覆蓋更新，目前共有 {len(data)} 筆管藥資料', 'success')
    except Exception as e: flash(f'更新失敗：{str(e)}', 'danger')
    return redirect(url_for('admin'))

@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    # [移除] 本地路徑設定
    pass
            
    pharmacists = request.form.get('pharmacists')
    if pharmacists is not None:
        update_setting('pharmacists', pharmacists)
        
    flash('設定已更新', 'success')
    return redirect(url_for('admin'))

@app.route('/upload_institutions', methods=['POST'])
def upload_institutions():
    if 'file' not in request.files: return 'No file'
    f = request.files['file']
    if f.filename == '': return 'No file'

    try:
        try:
            df = pd.read_csv(f, encoding='utf-8')
        except:
            df = pd.read_csv(f, encoding='cp950')
        
        count = import_institutions_from_df(df)
        flash(f'成功匯入 {count} 筆醫療機構資料', 'success')
    except Exception as e:
        flash(f'更新機構名冊失敗：{str(e)}', 'danger')

    return redirect(url_for('admin'))

@app.route('/history')
def history():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    q_type = request.args.get('q_type', 'patient')
    q_val = request.args.get('q_val', '').strip()
    
    # Defaults
    if not end_date: end_date = datetime.date.today().strftime('%Y-%m-%d')
    if not start_date: start_date = (datetime.date.today() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
    
    p_str = get_setting('pharmacists')
    pharmacists = [x.strip() for x in p_str.split(',') if x.strip()] if p_str else ['藥師A', '藥師B', '藥師C']
    
    conn = get_db()
    cur = conn.cursor()

    # Base query for PICKED drugs (history)
    # Postgres date logic: date(timestamp) works
    sub_sql = '''
        SELECT DISTINCT pd.prescription_id
        FROM prescription_drugs pd
        JOIN prescriptions p ON pd.prescription_id = p.id
        LEFT JOIN controlled_drugs cd ON pd.drug_code = cd.nh_code
        WHERE pd.status = '已領'
        AND date(pd.picked_at) BETWEEN %s AND %s
    '''
    sub_params = [start_date, end_date]

    if q_val:
        if q_type == 'patient':
            sub_sql += " AND p.patient_id LIKE %s"
            sub_params.append(f"%{q_val}%")
        elif q_type == 'drug':
            # Need to find matching NH codes first
            term = f"%{q_val}%"
            cur.execute("SELECT nh_code FROM controlled_drugs WHERE nh_code LIKE %s OR product_code LIKE %s OR barcode LIKE %s", (term, term, term))
            matched_rows = cur.fetchall()
            matched_codes = [r['nh_code'] for r in matched_rows]
            
            if matched_codes:
                placeholders = ','.join(['%s']*len(matched_codes))
                sub_sql += f" AND (pd.drug_code IN ({placeholders}) OR pd.drug_code LIKE %s)" 
                sub_params.extend(matched_codes)
                sub_params.append(term)
            else:
                sub_sql += " AND pd.drug_code LIKE %s"
                sub_params.append(term)

    # Main Query: Fetch ALL drugs for those prescriptions
    # Warning: sub_sql contains params, but we can't inject them easily into a text block if we execute separately.
    # Better to execute full query logic.
    # However, passing params into "IN (sub_sql)" is tricky if sub_sql has params.
    # We can perform the subquery first to get IDs.
    
    try:
        cur.execute(sub_sql, sub_params)
        p_ids = [str(r['prescription_id']) for r in cur.fetchall()]
        
        if not p_ids:
            grouped_results = []
        else:
            ids_placeholder = ','.join(['%s'] * len(p_ids))
            sql = f'''
                SELECT 
                    pd.id as pd_id, pd.picked_at, pd.picked_by, pd.drug_code, pd.picked_qty, pd.modified_by, pd.modified_at,
                    pd.status as drug_status,
                    pd.prescription_id as p_id,
                    p.patient_name, p.patient_id, p.visit_date, p.visit_seq, p.chronic_seq, p.chronic_total, p.institution_code, p.dept_code,
                    m.name as inst_name, d.name as dept_name,
                    cd.name as drug_name
                FROM prescription_drugs pd
                JOIN prescriptions p ON pd.prescription_id = p.id
                LEFT JOIN medical_institutions m ON p.institution_code = m.code
                LEFT JOIN departments d ON p.dept_code = d.code
                LEFT JOIN controlled_drugs cd ON pd.drug_code = cd.nh_code
                WHERE pd.prescription_id IN ({ids_placeholder})
                ORDER BY p.visit_date DESC, p.id DESC, pd.id ASC
            '''
            cur.execute(sql, p_ids)
            raw_results = [dict(row) for row in cur.fetchall()]
            
            groups = {} # pid -> {meta: ..., drugs: []}
            grouped_results = []
            
            for r in raw_results:
                pid = r['p_id']
                if pid not in groups:
                    groups[pid] = {
                        'meta': r, 
                        'drugs': []
                    }
                    grouped_results.append(groups[pid])
                
                groups[pid]['drugs'].append(r)
                
    except Exception as e:
        print(f"History Query Error: {e}")
        grouped_results = []
        
    conn.close()
    return render_template('history', start_date=start_date, end_date=end_date, q_type=q_type, q_val=q_val, results=grouped_results, pharmacists=pharmacists)

@app.route('/api/history/delete_group', methods=['POST'])
def history_delete_group():
    data = request.json
    p_id = data.get('p_id')
    try:
        conn = get_db()
        cur = conn.cursor()
        # Hard DELETE drugs first
        cur.execute("DELETE FROM prescription_drugs WHERE prescription_id = %s", (p_id,))
        # Hard DELETE prescription
        cur.execute("DELETE FROM prescriptions WHERE id = %s", (p_id,))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'msg': '已刪除紀錄'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

@app.route('/api/history/update', methods=['POST'])
def history_update():
    data = request.json
    p_id = data.get('p_id') # Prescription ID
    modifier = data.get('modifier')
    drugs = data.get('drugs', [])
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Update Drugs
        for d in drugs:
            cur.execute("""
                UPDATE prescription_drugs 
                SET picked_qty = %s, drug_code = %s, modified_by = %s, modified_at = %s 
                WHERE id = %s
            """, (d['qty'], d['code'], modifier, now_str, d['pd_id']))
        
        # 2. Update Prescription Details
        cur.execute("""
            UPDATE prescriptions 
            SET patient_name = %s, patient_id = %s, visit_date = %s, visit_seq = %s, 
                institution_code = %s, dept_code = %s, chronic_seq = %s, chronic_total = %s
            WHERE id = %s
        """, (
            data.get('p_name'), data.get('p_id_val'), data.get('visit_date'), data.get('visit_seq'),
            data.get('inst_code'), data.get('dept_code'), data.get('c_seq'), data.get('c_total'),
            p_id
        ))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'msg': '已更新紀錄'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'msg': str(e)})

# Removed api/import_now and api/transfer_file

@app.route('/api/keep_alive')
def keep_alive():
    return jsonify({'status': 'alive', 'timestamp': datetime.datetime.now().isoformat()})

def import_institutions_from_df(df):
    conn = get_db()
    cur = conn.cursor()
    data_to_insert = []
    for i, row in df.iterrows():
        try:
            code = str(row.iloc[1]).strip()
            name = str(row.iloc[3]).strip()
            if code and name and code.lower() != 'nan':
                data_to_insert.append((code, name))
        except:
            continue
    
    if data_to_insert:
        # [修改] 使用者要求「全覆蓋」
        cur.execute('DELETE FROM medical_institutions')
        cur.executemany('INSERT INTO medical_institutions (code, name) VALUES (%s, %s)', data_to_insert)
        conn.commit()
        print(f"成功載入 {len(data_to_insert)} 筆醫療機構資料。")
    conn.close()
    return len(data_to_insert)


if __name__ == '__main__':
    if not os.path.exists('uploads'): os.makedirs('uploads')
    # init_db() # Managed by migration
    
    app.run(host='0.0.0.0', port=5000, debug=False)