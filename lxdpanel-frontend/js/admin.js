/* ============================================================
   LXD Panel - Admin 管理端公共库
   - ADMIN.shell() 渲染侧边栏+顶栏+内容容器
   - ADMIN.request() 请求封装（同源 Cookie 会话，401 跳登录）
   ============================================================ */
(function () {
  'use strict';

  const ICONS = {
    dashboard: '◈', containers: '▤', templates: '▣', storage: '◫',
    users: '◉', tasks: '◷', brand: '✎', firewall: '◬', nginx: '⛨',
    ip: '◍', port: '⇄', menu: '☰', refresh: '↻', logout: '⎋', chevron: '▾',
    nodes: '⌘', products: '◈', orders: '◉', instances: '▣', tickets: '✉', mail: '✉', pay: '¤'
  };

  const MENUS = [
    { label: '概览', items: [{ id: 'dashboard', text: '仪表盘', href: 'dashboard.html', icon: ICONS.dashboard }] },
    {
      label: '商业化', items: [
        { id: 'nodes', text: '节点管理', href: 'nodes.html', icon: ICONS.nodes },
        { id: 'products', text: '商品管理', href: 'products.html', icon: ICONS.products },
        { id: 'orders', text: '订单管理', href: 'orders.html', icon: ICONS.orders },
        { id: 'instances', text: '实例管理', href: 'instances.html', icon: ICONS.instances },
        { id: 'tickets', text: '工单管理', href: 'tickets.html', icon: ICONS.tickets },
        { id: 'mail', text: '邮件配置', href: 'mail.html', icon: ICONS.mail },
        { id: 'pay', text: '支付配置', href: 'pay.html', icon: ICONS.pay }
      ]
    },
    {
      label: '容器', items: [
        { id: 'containers', text: '容器管理', href: 'containers.html', icon: ICONS.containers },
        { id: 'templates', text: '模板管理', href: 'templates.html', icon: ICONS.templates },
        { id: 'storage_pools', text: '存储池', href: 'storage_pools.html', icon: ICONS.storage }
      ]
    },
    { label: '用户', items: [{ id: 'users', text: '用户管理', href: 'users.html', icon: ICONS.users }] },
    {
      label: '网络', items: [
        { id: 'ip_pool_v4', text: 'IPv4 地址池', href: 'ip_pool_v4.html', icon: ICONS.ip },
        { id: 'ip_pool_v6', text: 'IPv6 地址池', href: 'ip_pool_v6.html', icon: ICONS.ip },
        { id: 'port_mapping_v4', text: '端口映射 IPv4', href: 'port_mapping_v4.html', icon: ICONS.port },
        { id: 'port_mapping_v6', text: '端口映射 IPv6', href: 'port_mapping_v6.html', icon: ICONS.port },
        { id: 'nginx', text: '反向代理', href: 'nginx.html', icon: ICONS.nginx }
      ]
    },
    {
      label: '系统', items: [
        { id: 'tasks', text: '任务管理', href: 'tasks.html', icon: ICONS.tasks },
        { id: 'brand_settings', text: '品牌设置', href: 'brand_settings.html', icon: ICONS.brand },
        { id: 'firewall', text: '防火墙', href: 'firewall.html', icon: ICONS.firewall }
      ]
    }
  ];

  /** 渲染管理端外壳（轻舟云风格：深色顶栏 + 面包屑 + 白色标签页子栏） */
  function shell(active, title, sub) {
    const app = document.getElementById('admin-app');
    if (!app) return;

    // 桌面端顶栏标签：单项组平铺，多项组悬停下拉
    const tabs = MENUS.map((group) => {
      if (group.items.length === 1) {
        const it = group.items[0];
        return '<a class="qz-tab' + (it.id === active ? ' is-active' : '') + '" href="' + it.href + '">' + it.text + '</a>';
      }
      const hasActive = group.items.some((it) => it.id === active);
      const items = group.items.map((it) => {
        return '<a class="qz-tabmenu-item' + (it.id === active ? ' is-active' : '') + '" href="' + it.href + '">' +
          '<span class="mi-icon">' + it.icon + '</span>' + it.text + '</a>';
      }).join('');
      return '<div class="qz-tabgroup' + (hasActive ? ' is-active' : '') + '">' +
        '<button type="button" class="qz-tab">' + group.label +
        ' <span class="mi-caret">' + ICONS.chevron + '</span></button>' +
        '<div class="qz-tabgroup-panel">' + items + '</div></div>';
    }).join('');

    // 移动端抽屉菜单（沿用原侧边栏）
    const drawer = MENUS.map((group) => {
      const items = group.items.map((it) => {
        return '<a class="menu-item' + (it.id === active ? ' active' : '') + '" href="' + it.href + '">' +
          '<span class="mi-icon">' + it.icon + '</span>' + it.text + '</a>';
      }).join('');
      return '<div class="menu-group-label">' + group.label + '</div>' + items;
    }).join('');

    app.innerHTML =
      '<div class="admin-shell">' +
      '<div class="side-overlay" id="sideOverlay"></div>' +
      '<aside class="admin-sidebar" id="adminSidebar">' +
      '  <div class="side-brand"><div class="brand-logo">L</div>' +
      '    <div><div class="side-brand-name">LXD 管理后台</div><div class="side-brand-sub">Admin Panel</div></div>' +
      '  </div>' +
      '  <nav class="side-nav">' + drawer + '</nav>' +
      '  <div class="side-foot">' +
      '    <div class="brand-logo" style="width:26px;height:26px;font-size:12px">A</div>' +
      '    <div style="flex:1;min-width:0"><div style="font-size:12.5px;font-weight:600;color:var(--side-text,#c3cad6)">管理员</div>' +
      '      <div style="font-size:11px;color:var(--side-text-2,#8a93a3)">LXD Panel</div></div>' +
      '    <button class="btn btn-ghost btn-sm js-admin-logout" title="退出登录">' + ICONS.logout + '</button>' +
      '  </div>' +
      '</aside>' +
      '<div class="admin-main">' +
      '  <header class="admin-topbar">' +
      '    <button class="btn btn-ghost btn-sm btn-menu" id="btnMenu">' + ICONS.menu + '</button>' +
      '    <a class="brand" href="dashboard.html">' +
      '      <div class="brand-logo" id="brandLogo">L</div>' +
      '      <div class="qz-brand-text"><strong id="brandName">LXD 管理后台</strong><em>Admin Console</em></div>' +
      '    </a>' +
      '    <span class="topbar-spacer"></span>' +
      '    <button class="btn btn-ghost btn-sm" id="btnRefresh" title="刷新">' + ICONS.refresh + '</button>' +
      '    <button class="btn btn-ghost btn-sm js-admin-logout" title="退出登录">' + ICONS.logout + '</button>' +
      '  </header>' +
      '  <div class="admin-crumbbar">' +
      '    <div class="admin-crumbbar-inner">' +
      '      <nav class="qz-crumb"><a href="dashboard.html">Home</a><i>/</i><span id="brandSub">LXD 管理后台</span><i>/</i><b>' + (title || '') + '</b></nav>' +
      '    </div>' +
      '  </div>' +
      '  <div class="admin-subbar">' +
      '    <div class="admin-subbar-inner">' +
      '      <nav class="qz-tabs">' + tabs + '</nav>' +
      '    </div>' +
      '  </div>' +
      '  <main class="admin-content" id="adminContent"></main>' +
      '</div></div>';

    // 移动端抽屉
    document.getElementById('btnMenu').addEventListener('click', () => {
      document.getElementById('adminSidebar').classList.add('open');
      document.getElementById('sideOverlay').classList.add('show');
    });
    document.getElementById('sideOverlay').addEventListener('click', () => {
      document.getElementById('adminSidebar').classList.remove('open');
      document.getElementById('sideOverlay').classList.remove('show');
    });
    document.querySelectorAll('.js-admin-logout').forEach((el) => el.addEventListener('click', ADMIN.logout));
    document.getElementById('btnRefresh').addEventListener('click', () => window.location.reload());

    // 分组下拉：点击开合 + 点击外部关闭（桌面同时支持悬停展开）
    document.querySelectorAll('.qz-tabgroup').forEach((group) => {
      const btn = group.querySelector('.qz-tab');
      if (!btn) return;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const wasOpen = group.classList.contains('is-open');
        document.querySelectorAll('.qz-tabgroup.is-open').forEach((g) => g.classList.remove('is-open'));
        if (!wasOpen) group.classList.add('is-open');
      });
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.qz-tabgroup')) {
        document.querySelectorAll('.qz-tabgroup.is-open').forEach((g) => g.classList.remove('is-open'));
      }
    });

    // 品牌
    LXD.loadBrand().then((b) => {
      LXD.applyBrand(b);
      document.title = (b.site_name || 'LXD 管理后台') + ' - ' + (title || '');
      const crumbName = document.getElementById('brandSub');
      if (crumbName) crumbName.textContent = b.site_name || 'LXD 管理后台';
    }).catch(() => {});
  }

  /** 请求封装（同源 Cookie 会话；返回 data 字段） */
  function request(url, options = {}) {
    options.method = options.method || 'GET';
    options.headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
    if (options.body && typeof options.body !== 'string') options.body = JSON.stringify(options.body);
    return fetch(url, options).then(async (res) => {
      if (res.status === 401 || res.status === 403) {
        ADMIN.toast('error', '登录已失效，请重新登录');
        setTimeout(() => { window.location.href = 'login.html'; }, 800);
        throw new Error('unauthorized');
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok || (data.code !== undefined && data.code !== 200)) {
        const err = new Error(data.msg || data.message || '请求失败');
        err.status = res.status; err.data = data;
        throw err;
      }
      return data;
    });
  }

  function logout() {
    fetch('/api/admin/logout', { method: 'POST' }).catch(() => {});
    setTimeout(() => { window.location.href = 'login.html'; }, 200);
  }

  /** 便捷工具 */
  const fmt = {
    bytes: LXD.fmtBytes,
    time: LXD.fmtTime,
    pct: (v) => (Math.round(v * 10) / 10) + '%'
  };

  /** 表格空态 */
  function empty(text) {
    return '<div class="empty"><div class="empty-icon">▫</div>' + LXD.esc(text || '暂无数据') + '</div>';
  }

  window.ADMIN = { shell, request, logout, fmt, empty, toast: LXD.toast, esc: LXD.esc, MENUS, ICONS };
})();
