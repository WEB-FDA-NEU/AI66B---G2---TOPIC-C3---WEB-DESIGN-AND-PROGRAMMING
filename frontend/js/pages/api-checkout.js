import { getItem, getProfile, getQuote, createBooking, getBooking, getBookingHold } from '../api.js';
import { accountHref, safeImageURL } from '../config.js';
import { requireLogin } from '../auth.js';
import { stayFromParams, parseRooms, fmtDate, guestText } from '../pricing.js';
import { formatVND } from '../render.js';
import { clearFieldErrors, setFieldError, toast } from '../ui.js';

const $ = id => document.getElementById(id);

export async function startApiCheckout(params) {
  // No card data is collected while no real provider exists.
  for (const id of ['cardNum','cardExp','cardCvv']) $(id)?.closest('.field')?.remove();
  document.querySelector('.booking-form-section').textContent = 'Xác nhận đặt phòng';
  document.querySelector('.booking-secure-note').textContent = 'Đặt phòng được xác nhận ngay sau khi lưu. Thanh toán tại homestay; không nhập thông tin thẻ.';
  const button = $('btnSubmit'); button.disabled = true;
  const message = $('formMsg');
  const showError = error => {
    if (error.status === 401) { requireLogin(); return; }
    message.hidden = false; message.textContent = error.detail || error.message || 'Không thực hiện được yêu cầu.';
  };
  const id = Number(params.get('id'));
  const back = accountHref(`detail.html?${params}#pricing`);
  $('backToSelect').href = $('editSelection').href = back;
  try {
    const me = await getProfile();
    const item = await getItem(id), stay = stayFromParams(params), selected = parseRooms(params.get('rooms'));
    const selections = Object.entries(selected).filter(([,qty])=>qty>0).map(([key,qty])=>({key,qty}));
    if (!selections.length) { location.replace(back); return; }
    const intent = params.get('intent') || crypto.randomUUID();
    if (!params.get('intent')) { params.set('intent',intent); history.replaceState(null,'',accountHref(`booking-page.html?${params}`)); }
    const storageKey = `luxstay_checkout_attempt_${me.id}_${intent}`;
    let previous;
    try { previous = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); } catch { throw Error('Yêu cầu cũ bị hỏng. Đối soát lịch sử trước khi đặt thêm.'); }
    if (previous?.bookingId) {
      const booking = await getBooking(previous.bookingId);
      location.replace(accountHref(`booking-confirmed.html?id=${booking.id}`)); return;
    }
    const quoteBody = {homestayId:id,checkIn:stay.checkin,checkOut:stay.checkout,adults:stay.adults,children:stay.children,rooms:selections};
    const holdTimer = $('checkout-hold-timer');
    let holdInterval;
    if (previous?.state !== 'sent') {
      const hold = await getBookingHold();
      const selectedIds = selections.map(selection => ({
        roomId: String(item.roomTypes.find(room => room.key === selection.key)?.id),
        qty: selection.qty,
      })).sort((a,b) => a.roomId.localeCompare(b.roomId));
      const heldIds = (hold?.rooms || []).map(selection => ({
        roomId: String(selection.roomId), qty: Number(selection.qty),
      })).sort((a,b) => a.roomId.localeCompare(b.roomId));
      if (!hold || Number(hold.homestayId) !== id || hold.checkIn !== stay.checkin
        || hold.checkOut !== stay.checkout || JSON.stringify(selectedIds) !== JSON.stringify(heldIds)) {
        showError(Error('Giữ chỗ đã hết hạn hoặc thay đổi. Quay lại lịch để chọn phòng và giữ chỗ lại.'));
        return;
      }
      const expiresAt = Date.parse(hold.expiresAt);
      const updateTimer = () => {
        const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
        holdTimer.hidden = false;
        holdTimer.textContent = remaining
          ? `Thời gian giữ chỗ còn ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}.`
          : 'Đã hết thời gian giữ chỗ. Quay lại lịch để chọn ngày và giữ phòng lại.';
        if (!remaining) {
          clearInterval(holdInterval);
          if (previous?.state !== 'sent') button.disabled = true;
        }
      };
      updateTimer();
      holdInterval = setInterval(updateTimer, 1000);
    }
    let currentQuote;
    const renderQuote = q => {
      currentQuote = q;
      $('nightsVal').textContent = `${q.nights} đêm`;
      $('roomLines').replaceChildren(...q.lines.map(line=>{
        const row=document.createElement('div');row.className='flex-between';
        const label=document.createElement('span');label.className='text-muted';label.textContent=`${line.qty} × ${line.name} × ${q.nights} đêm`;
        const amount=document.createElement('span');amount.textContent=formatVND(line.subtotal);row.append(label,amount);return row;
      }));
      $('roomSubtotalVal').textContent=formatVND(q.roomSubtotal);$('serviceFeeVal').textContent=formatVND(q.serviceFee);$('grandTotalVal').textContent=formatVND(q.total);
      button.textContent=`Đặt phòng ngay (${formatVND(q.total)})`;
    };
    $('sumImg').src=safeImageURL(item.cover_url);$('sumImg').alt=item.title;
    $('sumTitle').textContent=item.title;$('sumLocation').textContent=item.location || '';
    $('sumRatingWrap').hidden=item.rating==null;
    if(item.rating!=null){$('sumRating').textContent=item.rating.toFixed(1);$('sumRatingLabel').textContent='Đánh giá thực';$('sumRatingCount').textContent=`${item.review_count} đánh giá`;}
    $('checkinDisplay').textContent=fmtDate(stay.checkin);$('checkoutDisplay').textContent=fmtDate(stay.checkout);$('guestsVal').textContent=guestText(stay);
    $('accName').textContent=`Đã đăng nhập: ${me.display_name}`;$('accEmail').textContent=me.email;
    const names=me.display_name.trim().split(/\s+/);$('lastname').value=names.shift() || '';$('firstname').value=names.join(' ') || me.display_name;$('email').value=me.email;
    if (previous?.state === 'sent') {
      const original = previous.payload;
      if (JSON.stringify({...original,guestName:undefined,guestEmail:undefined}) !== JSON.stringify(quoteBody))
        throw Error('Ngày hoặc phòng khác yêu cầu chưa rõ kết quả. Mở lại URL yêu cầu gốc hoặc đối soát lịch sử.');
      $('firstname').value=original.guestName;$('firstname').readOnly=true;
      $('lastname').value='';$('lastname').required=false;$('lastname').closest('.field').hidden=true;
      $('email').value=original.guestEmail;$('email').readOnly=true;
    }
    // An uncertain retry must reach idempotency lookup even if its own booking filled inventory.
    if (previous?.state !== 'sent') renderQuote(await getQuote(quoteBody));
    else { button.textContent='Đối soát / gửi lại cùng yêu cầu'; message.hidden=false; message.textContent='Có yêu cầu chưa xác định kết quả. Gửi lại giữ nguyên key và nội dung, hoặc xem lịch sử đặt phòng.'; }
    button.disabled=false;
    $('checkoutForm').addEventListener('submit',async event=>{
      event.preventDefault(); if(button.disabled)return;
      clearFieldErrors($('checkoutForm'));message.hidden=true;
      let valid=true;
      for(const field of (previous?.state==='sent'?['firstname','email']:['lastname','firstname','email'])) if(!$(field).value.trim() || !$(field).validity.valid){setFieldError($(field),'Kiểm tra thông tin khách.');valid=false;}
      if(!valid)return;
      const payload=previous?.state==='sent'?previous.payload:{...quoteBody,guestName:`${$('firstname').value.trim()} ${$('lastname').value.trim()}`,guestEmail:$('email').value.trim()};
      const signature=JSON.stringify(payload);
      if(previous?.state==='sent' && previous.signature!==signature){showError(Error('Nội dung khác yêu cầu chưa rõ kết quả. Đối soát lịch sử trước khi tạo đơn mới.'));return;}
      button.disabled=true;button.textContent='Đang xử lý đặt phòng...';
      try {
        if(previous?.state!=='sent') {
          const fresh=await getQuote(quoteBody);
          const changed=currentQuote && fresh.total!==currentQuote.total;renderQuote(fresh);
          if(changed)throw Error('Giá đã thay đổi. Kiểm tra giá mới và xác nhận lại.');
        }
        const key=previous?.key || crypto.randomUUID();
        previous={key,payload,signature,state:'sent',createdAt:previous?.createdAt || Date.now()};
        sessionStorage.setItem(storageKey,JSON.stringify(previous));
        const booking=await createBooking(previous.payload,key);
        previous={key,signature,state:'complete',bookingId:booking.id};
        sessionStorage.setItem(storageKey,JSON.stringify(previous));
        toast('Đặt phòng đã được xác nhận.');
        location.href=accountHref(`booking-confirmed.html?id=${booking.id}`);
      } catch(error) { showError(error);button.disabled=false;button.textContent=previous?.state==='sent'?'Thử lại cùng yêu cầu':`Đặt phòng ngay (${formatVND(currentQuote.total)})`; }
    });
  } catch(error) { showError(error); }
}
