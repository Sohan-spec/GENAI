let allPosts = [];
let showingFollowing = false;
let currentCategory = "";
let likedIds = new Set(); // post IDs liked by current user

async function loadFeed() {
  let url = "/feed_api";
  const params = new URLSearchParams();
  
  if (showingFollowing) {
    params.append("following", "1");
  }
  
  if (currentCategory && currentCategory !== "") {
    params.append("category", currentCategory);
  }
  
  if (params.toString()) {
    url += "?" + params.toString();
  }
  try {
    console.log('Loading feed from:', url);
    const res = await fetch(url);
    console.log('Response status:', res.status);
    
    if (!res.ok) {
      console.error('Response not OK:', res.status, res.statusText);
      if (res.status === 401) {
        showNotice('Please log in and follow artists to use Followers Only.');
        showingFollowing = false;
        currentCategory = "";
        updateFilterStyles();
        // Load all posts instead of recursive call
        const resAll = await fetch('/feed_api');
        const dataAll = await resAll.json().catch(() => []);
        allPosts = Array.isArray(dataAll) ? dataAll : [];
        renderFeed(allPosts);
        return;
      }
      showNotice('Failed to load feed. Showing All.');
      showingFollowing = false;
      currentCategory = "";
      updateFilterStyles();
      const resAll = await fetch('/feed_api');
      const dataAll = await resAll.json().catch(() => []);
      allPosts = Array.isArray(dataAll) ? dataAll : [];
      renderFeed(allPosts);
      return;
    }
    
    const data = await res.json();
    console.log('Received data:', data);
    allPosts = Array.isArray(data) ? data : [];
    console.log('Processed posts:', allPosts.length);
    renderFeed(allPosts);
    // After rendering, wire up like buttons
    attachLikeHandlers();
  } catch (err) {
    console.error('Error loading feed:', err);
    showNotice('Network error loading feed.');
    // Try to load all posts as fallback
    try {
      const resAll = await fetch('/feed_api');
      const dataAll = await resAll.json().catch(() => []);
      allPosts = Array.isArray(dataAll) ? dataAll : [];
      renderFeed(allPosts);
      attachLikeHandlers();
    } catch (fallbackErr) {
      console.error('Fallback also failed:', fallbackErr);
      allPosts = [];
      renderFeed(allPosts);
    }
  }
}

function renderFeed(posts) {
  console.log('Rendering feed with posts:', posts);
  const container = document.getElementById("feed");
  if (!container) {
    console.error('Feed container not found!');
    return;
  }
  
  if (!posts || posts.length === 0) {
    container.innerHTML = '<p style="text-align: center; color: var(--muted); padding: 40px;">No posts found.</p>';
    return;
  }
  
  container.innerHTML = posts.map(p => {
    const liked = likedIds.has(p.id);
    const heart = liked ? '❤' : '♡';
    const heartTitle = liked ? 'Unlike' : 'Like';
    return `
    <a class="card" href="/post/${p.id}">
      ${p.image 
        ? `<img src="${p.image}" alt="art" />` 
        : `<div style="height:220px;background:#f3f4f6"></div>`}
      <div class="card-body">
        <div class="title-row" style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
          <div class="title">${p.title ? escapeHtml(p.title) : "Untitled"}</div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="like-count" data-post-id="${p.id}" style="color:#6b7280; font-weight:600;">${Number(p.like_count || 0)}</span>
            <button class="like-btn" data-post-id="${p.id}" title="${heartTitle}"
              style="min-width:48px;height:44px;border:1px solid var(--border);border-radius:12px;background:#fff;color:${liked ? '#e11d48' : '#6b7280'};cursor:pointer;font-size:22px;line-height:1;">
              ${heart}
            </button>
          </div>
        </div>
        <div class="artist">
          👤 ${p.artist ? escapeHtml(p.artist) : "Unknown artist"}
        </div>
        <div class="category" style="margin-top: 4px; font-size: 14px; color: var(--accent); font-weight: 600;">
          🏷️ ${p.category ? escapeHtml(p.category) : "None"}
        </div>
        ${p.price ? `
          <div class="price">
            💰 ${escapeHtml(p.price)}
          </div>` : ""}
      </div>
    </a>`;
  }).join("");
  console.log('Feed rendered successfully');
}




function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setupSearch() {
  const input = document.getElementById("searchInput");
  if (!input) return;
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase();
    const filtered = allPosts.filter(p =>
      (p.title || "").toLowerCase().includes(q) ||
      (p.artist || "").toLowerCase().includes(q) ||
      (p.category || "").toLowerCase().includes(q) ||
      (p.created_at || "").toLowerCase().includes(q)
    );
    renderFeed(filtered);
  });
}

function setupFilters() {
  const btnAll = document.getElementById('filterAll');
  const btnFollowing = document.getElementById('filterFollowing');
  const btnPaintings = document.getElementById('filterPaintings');
  const btnVases = document.getElementById('filterVases');
  const btnArt = document.getElementById('filterArt');
  const btnCups = document.getElementById('filterCups');
  
  if (btnAll) {
    btnAll.addEventListener('click', async () => {
      showingFollowing = false;
      currentCategory = "";
      updateFilterStyles();
      await loadFeed();
    });
  }
  if (btnFollowing) {
    btnFollowing.addEventListener('click', async () => {
      showingFollowing = true;
      currentCategory = "";
      updateFilterStyles();
      await loadFeed();
    });
  }
  if (btnPaintings) {
    btnPaintings.addEventListener('click', async () => {
      showingFollowing = false;
      currentCategory = "Paintings";
      updateFilterStyles();
      await loadFeed();
    });
  }
  if (btnVases) {
    btnVases.addEventListener('click', async () => {
      showingFollowing = false;
      currentCategory = "Vases";
      updateFilterStyles();
      await loadFeed();
    });
  }
  if (btnArt) {
    btnArt.addEventListener('click', async () => {
      showingFollowing = false;
      currentCategory = "Art";
      updateFilterStyles();
      await loadFeed();
    });
  }
  if (btnCups) {
    btnCups.addEventListener('click', async () => {
      showingFollowing = false;
      currentCategory = "Cups";
      updateFilterStyles();
      await loadFeed();
    });
  }
}

function updateFilterStyles() {
  const btnAll = document.getElementById('filterAll');
  const btnFollowing = document.getElementById('filterFollowing');
  const btnPaintings = document.getElementById('filterPaintings');
  const btnVases = document.getElementById('filterVases');
  const btnArt = document.getElementById('filterArt');
  const btnCups = document.getElementById('filterCups');
  
  // Remove active class from all buttons
  [btnAll, btnFollowing, btnPaintings, btnVases, btnArt, btnCups].forEach(btn => {
    if (btn) btn.classList.remove('active');
  });
  
  // Add active class to the appropriate button
  if (showingFollowing) {
    if (btnFollowing) btnFollowing.classList.add('active');
  } else if (currentCategory === "Paintings") {
    if (btnPaintings) btnPaintings.classList.add('active');
  } else if (currentCategory === "Vases") {
    if (btnVases) btnVases.classList.add('active');
  } else if (currentCategory === "Art") {
    if (btnArt) btnArt.classList.add('active');
  } else if (currentCategory === "Cups") {
    if (btnCups) btnCups.classList.add('active');
  } else {
    if (btnAll) btnAll.classList.add('active');
  }
}

// ----- Likes helpers -----
async function loadLikedIds() {
  try {
    const res = await fetch('/api/my_liked_ids');
    if (!res.ok) {
      likedIds = new Set();
      return;
    }
    const ids = await res.json();
    if (Array.isArray(ids)) {
      likedIds = new Set(ids);
    }
  } catch (e) {
    likedIds = new Set();
  }
}

function attachLikeHandlers() {
  const buttons = document.querySelectorAll('.like-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const postId = parseInt(btn.getAttribute('data-post-id'), 10);
      const isLiked = likedIds.has(postId);
      try {
        const url = isLiked ? '/api/unlike' : '/api/like';
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `post_id=${encodeURIComponent(postId)}`
        });
        if (res.status === 401) {
          showNotice('Please log in to like posts.');
          return;
        }
        const data = await res.json();
        if (data && data.status === 'ok') {
          if (isLiked) {
            likedIds.delete(postId);
          } else {
            likedIds.add(postId);
          }
          // Update button UI without re-rendering entire feed
          const nowLiked = likedIds.has(postId);
          btn.textContent = nowLiked ? '❤' : '♡';
          btn.style.color = nowLiked ? '#e11d48' : '#6b7280';
          btn.title = nowLiked ? 'Unlike' : 'Like';
          // Update count
          const countEl = document.querySelector(`.like-count[data-post-id="${postId}"]`);
          if (countEl) {
            const current = parseInt(countEl.textContent || '0', 10) || 0;
            countEl.textContent = String(current + (nowLiked ? 1 : -1));
          }
        } else {
          showNotice('Error updating like.');
        }
      } catch (err) {
        showNotice('Network error.');
      }
    });
  });
}

// Initial load with retry mechanism
async function initializeFeed() {
  try {
    await loadLikedIds();
    await loadFeed();
  } catch (err) {
    console.error('Initial feed load failed:', err);
    // Try one more time after a short delay
    setTimeout(async () => {
      try {
        await loadFeed();
      } catch (retryErr) {
        console.error('Retry also failed:', retryErr);
        // Show empty state
        const container = document.getElementById("feed");
        if (container) {
          container.innerHTML = '<p style="text-align: center; color: var(--muted); padding: 40px;">Unable to load posts. Please refresh the page.</p>';
        }
      }
    }, 1000);
  }
}

initializeFeed();
setupSearch();
setupFilters();
updateFilterStyles();

function showNotice(message) {
  let el = document.getElementById('notice');
  if (!el) {
    el = document.createElement('div');
    el.id = 'notice';
    el.style.position = 'fixed';
    el.style.top = '16px';
    el.style.right = '16px';
    el.style.padding = '10px 12px';
    el.style.borderRadius = '10px';
    el.style.background = 'linear-gradient(135deg, var(--accent), var(--accent-2))';
    el.style.color = '#fff';
    el.style.boxShadow = '0 6px 16px rgba(0,0,0,0.15)';
    el.style.zIndex = '9999';
    el.style.transition = 'opacity 0.3s ease';
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.style.opacity = '1';
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => { 
    el.style.opacity = '0';
    // Remove from DOM after fade out
    setTimeout(() => {
      if (el && el.parentNode) {
        el.parentNode.removeChild(el);
      }
    }, 300);
  }, 2500);
}
