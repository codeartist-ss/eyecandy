-- eyecandy schema for Supabase (Postgres)
-- Run this in the Supabase SQL Editor.

create table app_user (
    user_id serial primary key,
    name varchar(100) not null,
    email varchar(150) not null unique,
    password_hash varchar(255) not null,
    role varchar(10) not null default 'buyer' check (role in ('buyer','seller','both')),
    profile_pic varchar(500),
    bio text,
    joined_at timestamp default current_timestamp
);

create table buyer (
    buyer_id serial primary key,
    user_id int not null unique references app_user(user_id) on delete cascade,
    default_size varchar(20),
    preferred_gender varchar(10) check (preferred_gender in ('men','women','unisex','kids'))
);

create table seller (
    seller_id serial primary key,
    user_id int not null unique references app_user(user_id) on delete cascade,
    store_name varchar(150) not null,
    store_url varchar(500),
    verified boolean default false
);

create table category (
    category_id serial primary key,
    name varchar(100) not null,
    parent_category_id int references category(category_id) on delete set null
);

create table clothing_item (
    item_id serial primary key,
    seller_id int not null references seller(seller_id) on delete cascade,
    category_id int not null references category(category_id) on delete restrict,
    title varchar(200) not null,
    description text,
    price decimal(10,2) not null check (price >= 0),
    brand varchar(100),
    gender varchar(10) default 'women' check (gender in ('men','women','unisex','kids')),
    buy_link varchar(500) not null,
    uploaded_at timestamp default current_timestamp
);

create table item_image (
    image_id serial primary key,
    item_id int not null references clothing_item(item_id) on delete cascade,
    image_url varchar(500) not null,
    is_primary boolean default false
);

-- Only one PRIMARY image per item is allowed; multiple non-primary images are fine.
create unique index ux_item_image_one_primary
    on item_image (item_id)
    where is_primary = true;

create table board (
    board_id serial primary key,
    user_id int not null references app_user(user_id) on delete cascade,
    name varchar(150) not null,
    board_type varchar(10) not null default 'wishlist' check (board_type in ('closet','wishlist')),
    is_private boolean default false,
    created_at timestamp default current_timestamp,
    check (board_type != 'closet' or is_private = false)
);

create table board_item (
    board_id int not null references board(board_id) on delete cascade,
    item_id  int not null references clothing_item(item_id) on delete cascade,
    primary key (board_id, item_id)
);

create table closet_item (
    closet_item_id serial primary key,
    board_id int not null references board(board_id) on delete cascade,
    item_id int references clothing_item(item_id) on delete set null,
    custom_title varchar(200),
    store_link varchar(500) not null,
    image_url varchar(500),
    purchased_at date,
    notes text,
    added_at timestamp default current_timestamp
);

create table orders (
    order_id serial primary key,
    buyer_id int not null references buyer(buyer_id) on delete restrict,
    item_id int not null references clothing_item(item_id) on delete restrict,
    size varchar(20),
    quantity int not null default 1 check (quantity > 0),
    status varchar(10) default 'pending' check (status in ('pending','confirmed','shipped','delivered','cancelled')),
    ordered_at timestamp default current_timestamp
);

create table likes (
    like_id serial primary key,
    user_id int not null references app_user(user_id) on delete cascade,
    item_id int not null references clothing_item(item_id) on delete cascade,
    liked_at timestamp default current_timestamp,
    unique (user_id, item_id)
);

create table comment (
    comment_id serial primary key,
    user_id int not null references app_user(user_id) on delete cascade,
    item_id int not null references clothing_item(item_id) on delete cascade,
    content text not null,
    posted_at timestamp default current_timestamp
);

-- ── Seed data ─────────────────────────────────────────────────────────────

insert into category (name, parent_category_id) values
('tops', null),
('bottoms', null),
('dresses', null),
('outerwear', null),
('shoes', null),
('accessories', null),
('modest wear', null),
('formal', null),
('blouses', 1),
('t-shirts', 1),
('jeans', 2),
('trousers', 2),
('midi dress', 3),
('maxi dress', 3),
('abaya', 7),
('kurta set', 7);

-- NOTE: these password hashes are placeholders. Real signups via the app will
-- generate proper werkzeug hashes; these seed accounts are for demo browsing
-- only and won't be able to log in until you set real hashes or re-signup.
insert into app_user (name, email, password_hash, role, bio) values
('ayesha zara', 'ayesha@example.com', 'unset', 'both', 'fashion lover from lahore'),
('sana mirza', 'sana@example.com', 'unset', 'buyer', 'minimalist wardrobe goals'),
('rida khan', 'rida@example.com', 'unset', 'buyer', 'modest fashion enthusiast'),
('zara boutique', 'zara_b@example.com', 'unset', 'seller', null),
('khaadi official', 'khaadi@example.com', 'unset', 'seller', null);

insert into buyer (user_id, default_size, preferred_gender) values
(1, 'S', 'women'),
(2, 'XS', 'women'),
(3, 'M', 'women');

insert into seller (user_id, store_name, store_url, verified) values
(1, 'ayesha styles', 'https://ayeshastyles.pk', false),
(4, 'zara boutique', 'https://zara.com/pk', true),
(5, 'khaadi', 'https://khaadi.com', true);

insert into clothing_item (seller_id, category_id, title, description, price, brand, gender, buy_link) values
(2, 9, 'linen wrap blouse', 'breathable summer blouse in 3 colours', 4200.00, 'zara', 'women', 'https://zara.com/pk/linen-wrap-blouse'),
(3, 16, 'embroidered kurta set', '3-piece eid collection', 8500.00, 'khaadi', 'women', 'https://khaadi.com/kurta-set-eid'),
(3, 15, 'silk abaya camel', 'premium silk relaxed fit', 12000.00, 'khaadi', 'women', 'https://khaadi.com/silk-abaya-camel'),
(2, 12, 'pleated midi skirt', 'high-waist pleated skirt', 2800.00, 'zara', 'women', 'https://zara.com/pk/pleated-midi-skirt'),
(1, 4, 'oversized denim jacket', 'classic oversized fit', 6100.00, 'h&m', 'unisex', 'https://hm.com/pk/denim-jacket'),
(2, 12, 'wide-leg trousers', 'flowy wide-leg trousers', 3500.00, 'sapphire', 'women', 'https://sapphire.pk/wide-leg-trousers');

insert into item_image (item_id, image_url, is_primary) values
(1, 'https://i.pinimg.com/736x/9d/23/2b/9d232bdf66c28a0df156f23562e59229.jpg', true),
(1, 'https://cdn.eyecandy.pk/imgs/linen-blouse-back.jpg', false),
(2, 'https://cdn.eyecandy.pk/imgs/kurta-set-main.jpg', true),
(3, 'https://cdn.eyecandy.pk/imgs/abaya-camel-front.jpg', true),
(4, 'https://cdn.eyecandy.pk/imgs/midi-skirt-main.jpg', true),
(5, 'https://cdn.eyecandy.pk/imgs/denim-jacket-main.jpg', true),
(6, 'https://cdn.eyecandy.pk/imgs/wide-leg-trousers.jpg', true);

insert into board (user_id, name, board_type, is_private) values
(1, 'my closet', 'closet', false),
(2, 'my closet', 'closet', false),
(3, 'my closet', 'closet', false),
(1, 'summer inspo', 'wishlist', false),
(1, 'eid wishlist', 'wishlist', false),
(2, 'office looks', 'wishlist', false),
(3, 'modest fashion', 'wishlist', false),
(2, 'secret wishlist', 'wishlist', true);

insert into closet_item (board_id, item_id, custom_title, store_link, purchased_at, notes) values
(1, 1, null, 'https://zara.com/pk/linen-wrap-blouse', '2025-03-10', 'got it in the sale!'),
(1, 5, null, 'https://hm.com/pk/denim-jacket', '2025-01-22', 'perfect for winter layering'),
(1, null, 'floral coord set', 'https://generation.com.pk/floral-coord', '2024-12-05', 'wore this to a wedding'),
(2, 4, null, 'https://zara.com/pk/pleated-midi-skirt', '2025-02-14', null),
(3, 2, null, 'https://khaadi.com/kurta-set-eid', '2025-03-28', 'wore for eid day 1'),
(3, 3, null, 'https://khaadi.com/silk-abaya-camel', '2025-03-20', 'favourite abaya ever');

insert into board_item (board_id, item_id) values
(4, 3), (4, 6), (5, 2), (5, 3), (6, 1), (6, 4), (7, 3), (8, 5);

insert into orders (buyer_id, item_id, size, quantity, status) values
(2, 1, 'S', 1, 'delivered'),
(3, 2, 'M', 1, 'delivered'),
(1, 6, 'M', 1, 'shipped'),
(2, 4, 'XS', 1, 'pending');

insert into likes (user_id, item_id) values
(1, 2), (1, 3), (2, 1), (2, 3), (2, 5), (3, 1), (3, 2), (3, 3);

insert into comment (user_id, item_id, content) values
(2, 1, 'obsessed with this blouse, is it true to size?'),
(1, 1, 'yes totally true to size! i got a small'),
(3, 2, 'the embroidery on this is beautiful'),
(1, 3, 'does this come in black too?'),
(2, 5, 'need this jacket in my life asap');
