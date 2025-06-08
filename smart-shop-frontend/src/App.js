import React, { useState, useEffect } from 'react';
import { ShoppingCart, Search, User, X, Plus, Check, LogOut } from 'lucide-react';
import './App.css';

// Конфигурация API
const API_BASE_URL = 'http://localhost:8000';

// Утилиты для работы с API
const apiRequest = async (endpoint, options = {}) => {
  const token = localStorage.getItem('token');
  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: { ...defaultHeaders, ...options.headers },
    ...options
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network error' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }

  return response.json();
};

// Компонент уведомления
const Notification = ({ message, type, onClose }) => (
  <div className={`fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
    type === 'success' ? 'bg-green-500' : 'bg-red-500'
  } text-white max-w-md`}>
    <div className="flex items-center justify-between">
      <span>{message}</span>
      <button onClick={onClose} className="ml-2">
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
);

// Компонент карточки товара
const ProductCard = ({ product, onAddToCart, showAddButton = true }) => (
  <div className="bg-white rounded-lg shadow-md p-4 border hover:shadow-lg transition-shadow">
    <div className="text-4xl mb-2 text-center">
      {product.emoji || getEmojiForProduct(product.name)}
    </div>
    <h3 className="font-semibold text-sm text-center mb-1">{product.name}</h3>
    {product.aisle_name && (
      <p className="text-xs text-gray-500 text-center mb-1">{product.aisle_name}</p>
    )}
    {product.department_name && (
      <p className="text-xs text-gray-400 text-center mb-3">{product.department_name}</p>
    )}
    {showAddButton && (
      <button
        onClick={() => onAddToCart(product)}
        className="w-full bg-blue-500 hover:bg-blue-600 text-white text-xs py-2 px-3 rounded transition-colors flex items-center justify-center gap-1"
      >
        <Plus className="w-3 h-3" />
        Заказ
      </button>
    )}
  </div>
);

// Функция для получения эмодзи товара
const getEmojiForProduct = (productName) => {
  const emojiMap = {
    'banana': '🍌', 'apple': '🍎', 'orange': '🍊', 'avocado': '🥑',
    'milk': '🥛', 'cheese': '🧀', 'yogurt': '🥤', 'egg': '🥚',
    'bread': '🍞', 'bagel': '🥯', 'pizza': '🍕',
    'carrot': '🥕', 'tomato': '🍅', 'cucumber': '🥒', 'pepper': '🌶️',
    'meat': '🥩', 'chicken': '🍗', 'fish': '🐟',
    'rice': '🍚', 'pasta': '🍝', 'cereal': '🥣'
  };

  const name = productName.toLowerCase();
  for (const [key, emoji] of Object.entries(emojiMap)) {
    if (name.includes(key)) return emoji;
  }
  return '🛒'; // дефолтный эмодзи
};

// Компонент корзины
const CartItem = ({ item, onUpdateQuantity, onRemove }) => (
  <div className="flex items-center justify-between py-2 border-b">
    <div className="flex items-center gap-2">
      <span className="text-sm">{getEmojiForProduct(item.name)}</span>
      <span className="text-sm">{item.name}</span>
    </div>
    <div className="flex items-center gap-2">
      <button
        onClick={() => onUpdateQuantity(item.id, Math.max(0, item.quantity - 1))}
        className="w-6 h-6 bg-gray-200 rounded text-xs flex items-center justify-center hover:bg-gray-300"
      >
        -
      </button>
      <span className="text-sm font-medium">{item.quantity}</span>
      <button
        onClick={() => onUpdateQuantity(item.id, item.quantity + 1)}
        className="w-6 h-6 bg-gray-200 rounded text-xs flex items-center justify-center hover:bg-gray-300"
      >
        +
      </button>
      <button
        onClick={() => onRemove(item.id)}
        className="text-red-500 ml-2 hover:text-red-700"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  </div>
);

// Модальное окно подтверждения заказа
const OrderConfirmModal = ({ isOpen, orderData, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <div className="text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-500" />
          </div>
          <h2 className="text-xl font-bold mb-2">ЗАКАЗ ОФОРМЛЕН!</h2>
          <p className="text-gray-600 mb-4">Заказ #{orderData.order_id} успешно создан</p>

          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <h3 className="font-semibold mb-2">В заказе:</h3>
            {orderData.items.map((item, index) => (
              <div key={index} className="text-sm text-gray-700">
                • {item.product_name} x{item.quantity}
              </div>
            ))}
          </div>

          <p className="text-sm text-gray-600 mb-6">
            {orderData.message}
          </p>

          <button
            onClick={onClose}
            className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
          >
            ОТЛИЧНО
          </button>
        </div>
      </div>
    </div>
  );
};

const SmartShop = () => {
  const [currentPage, setCurrentPage] = useState('login');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);
  const [cart, setCart] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [popularProducts, setPopularProducts] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const [filteredProducts, setFilteredProducts] = useState([]);
  const [userStats, setUserStats] = useState(null);
  const [notification, setNotification] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [orderConfirmModal, setOrderConfirmModal] = useState({ isOpen: false, data: null });
  const [searchQuery, setSearchQuery] = useState('');
  const [authForm, setAuthForm] = useState({
    email: '',
    password: '',
    name: ''
  });

  // Проверяем токен и восстанавливаем состояние при загрузке
  useEffect(() => {
    checkAuthStatus();

    // Восстанавливаем корзину из localStorage
    const savedCart = localStorage.getItem('cart');
    if (savedCart) {
      setCart(JSON.parse(savedCart));
    }
  }, []);

  // Сохраняем корзину при изменении
  useEffect(() => {
    if (cart.length > 0) {
      localStorage.setItem('cart', JSON.stringify(cart));
    } else {
      localStorage.removeItem('cart');
    }
  }, [cart]);

  // Поиск товаров
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredProducts([]);
    } else {
      searchProducts(searchQuery);
    }
  }, [searchQuery]);

  const checkAuthStatus = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const userData = await apiRequest('/auth/me');
        setUser(userData);
        setIsLoggedIn(true);
        setCurrentPage('main');

        // Восстанавливаем сохраненные данные
        const savedRecommendations = localStorage.getItem('recommendations');
        const savedPopular = localStorage.getItem('popularProducts');

        if (savedRecommendations) {
          setRecommendations(JSON.parse(savedRecommendations));
        }
        if (savedPopular) {
          setPopularProducts(JSON.parse(savedPopular));
        }

        // Загружаем свежие данные
        loadMainPageData();
      } catch (error) {
        localStorage.removeItem('token');
        localStorage.removeItem('recommendations');
        localStorage.removeItem('popularProducts');
        localStorage.removeItem('userStats');
        console.error('Auth check failed:', error);
      }
    }
  };

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };


  const loadMainPageData = async () => {
    try {
      setIsLoading(true);

      // Загружаем коллаборативные рекомендации с исключением популярных товаров
      try {
        const recommendationsData = await apiRequest('/recommendations/?model_type=collaborative&limit=10&exclude_popular=true');

        // Проверяем, что это действительно персональные рекомендации, а не fallback
        if (recommendationsData.length > 0 && recommendationsData[0].model_type === 'collaborative') {
          setRecommendations(recommendationsData);
          localStorage.setItem('recommendations', JSON.stringify(recommendationsData));
        } else {
          setRecommendations([]);
          localStorage.removeItem('recommendations');
        }
      } catch (error) {
        console.error('Failed to load recommendations:', error);
        setRecommendations([]);
        localStorage.removeItem('recommendations');
      }

      // Загружаем популярные товары через endpoint рекомендаций
      try {
        const popularData = await apiRequest('/recommendations/?model_type=popular&limit=10');
        setPopularProducts(popularData);
        // Сохраняем в localStorage
        localStorage.setItem('popularProducts', JSON.stringify(popularData));
      } catch (error) {
        console.error('Failed to load popular products:', error);
        // Если не удалось загрузить через рекомендации, пробуем через продукты
        try {
          const productsData = await apiRequest('/products/?limit=10');
          // Преобразуем формат для совместимости
          const formattedProducts = productsData.map(p => ({
            product_id: p.id,
            product_name: p.name,
            aisle_name: p.aisle_name,
            department_name: p.department_name,
            score: 0.5
          }));
          setPopularProducts(formattedProducts);
        } catch (err) {
          console.error('Failed to load products:', err);
          setPopularProducts([]);
        }
      }

      // Загружаем все товары для поиска
      try {
        const allProductsData = await apiRequest('/products/?limit=100');
        setAllProducts(allProductsData);
      } catch (error) {
        console.error('Failed to load all products:', error);
      }

      // Загружаем статистику пользователя
      try {
        const userPreferences = await apiRequest('/recommendations/preferences');
        setUserStats({
          favoriteCategory: userPreferences.favorite_departments[0] || 'Не определено',
          monthlyOrders: userPreferences.total_orders,
          frequentProducts: userPreferences.most_ordered_products.slice(0, 3).map(p => p.name)
        });

        // Сохраняем статистику в localStorage
        localStorage.setItem('userStats', JSON.stringify({
          favoriteCategory: userPreferences.favorite_departments[0] || 'Не определено',
          monthlyOrders: userPreferences.total_orders,
          frequentProducts: userPreferences.most_ordered_products.slice(0, 3).map(p => p.name)
        }));
      } catch (error) {
        console.error('Failed to load user preferences:', error);
        // Пробуем загрузить из localStorage
        const savedStats = localStorage.getItem('userStats');
        if (savedStats) {
          setUserStats(JSON.parse(savedStats));
        }
      }

    } catch (error) {
      console.error('Failed to load main page data:', error);
      showNotification('Ошибка загрузки данных', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const searchProducts = async (query) => {
    try {
      const searchResults = await apiRequest(`/products/?search=${encodeURIComponent(query)}&limit=20`);
      setFilteredProducts(searchResults);
    } catch (error) {
      console.error('Search failed:', error);
      setFilteredProducts([]);
    }
  };

  const handleLogin = async () => {
    if (!authForm.email || !authForm.password) {
      showNotification('Заполните все поля', 'error');
      return;
    }

    if (!authForm.email.includes('@')) {
      showNotification('Введите корректный email', 'error');
      return;
    }

    setIsLoading(true);

    try {
      const loginData = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: authForm.email,
          password: authForm.password
        })
      });

      localStorage.setItem('token', loginData.access_token);
      setUser(loginData.user || { name: authForm.email.split('@')[0], email: authForm.email });
      setIsLoggedIn(true);
      setCurrentPage('main');
      await loadMainPageData();
      showNotification(`Добро пожаловать, ${loginData.user?.name || authForm.email.split('@')[0]}!`);
      setAuthForm({ email: '', password: '', name: '' });
    } catch (error) {
      if (error.message.includes('401') || error.message.includes('Invalid')) {
        showNotification('Неверный email или пароль', 'error');
      } else {
        showNotification(error.message, 'error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!authForm.email || !authForm.password || !authForm.name) {
      showNotification('Заполните все поля', 'error');
      return;
    }

    if (!authForm.email.includes('@')) {
      showNotification('Введите корректный email', 'error');
      return;
    }

    if (authForm.password.length < 6) {
      showNotification('Пароль должен быть не менее 6 символов', 'error');
      return;
    }

    setIsLoading(true);

    try {
      await apiRequest('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          email: authForm.email,
          password: authForm.password,
          name: authForm.name
        })
      });

      showNotification('Регистрация успешна! Теперь войдите в систему.');
      setCurrentPage('login');
      setAuthForm({ email: authForm.email, password: '', name: '' });
    } catch (error) {
      if (error.message.includes('409') || error.message.includes('already exists')) {
        showNotification('Пользователь с таким email уже существует', 'error');
      } else {
        showNotification(error.message, 'error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('cart');
    localStorage.removeItem('recommendations');
    localStorage.removeItem('popularProducts');
    localStorage.removeItem('userStats');
    setIsLoggedIn(false);
    setUser(null);
    setCart([]);
    setCurrentPage('login');
    setAuthForm({ email: '', password: '', name: '' });
    setSearchQuery('');
    showNotification('Вы вышли из системы');
  };

  const addToCart = (product) => {
    setCart(prevCart => {
      const existingItem = prevCart.find(item => item.id === product.id);
      if (existingItem) {
        return prevCart.map(item =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prevCart, { ...product, quantity: 1 }];
    });
    showNotification(`${product.name} добавлен в заказ`);
  };

  const updateCartQuantity = (productId, newQuantity) => {
    if (newQuantity === 0) {
      removeFromCart(productId);
      return;
    }
    setCart(prevCart =>
      prevCart.map(item =>
        item.id === productId ? { ...item, quantity: newQuantity } : item
      )
    );
  };

  const removeFromCart = (productId) => {
    setCart(prevCart => prevCart.filter(item => item.id !== productId));
  };

  const clearCart = () => {
    setCart([]);
    showNotification('Заказ очищен');
  };

  const submitOrder = async () => {
    if (cart.length === 0) {
      showNotification('Корзина пуста', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const orderData = await apiRequest('/orders/', {
        method: 'POST',
        body: JSON.stringify({
          items: cart.map(item => ({
            product_id: item.id,
            quantity: item.quantity
          }))
        })
      });

      setOrderConfirmModal({ isOpen: true, data: orderData });
      setCart([]);

      // Перезагружаем данные после заказа для обновления статистики
      setTimeout(() => {
        loadMainPageData();
      }, 1000);
    } catch (error) {
      showNotification(error.message, 'error');
    } finally {
      setIsLoading(false);
    }
  };


  const generateRecommendations = async () => {
    setIsLoading(true);
    try {
      const response = await apiRequest('/recommendations/generate/collaborative', {
        method: 'POST'
      });

      console.log('Generate recommendations response:', response);

      if (response.status === 'success' && response.count > 0) {
        showNotification('Рекомендации успешно сгенерированы!');

        // Ждем немного перед перезагрузкой
        setTimeout(async () => {
          await loadMainPageData();
        }, 1500);
      } else if (response.status === 'no_orders') {
        showNotification(response.message, 'error');
      } else {
        showNotification('Рекомендации сгенерированы, но пока пусты. Попробуйте сделать еще несколько заказов.', 'error');
      }
    } catch (error) {
      console.error('Generate recommendations error:', error);
      showNotification('Ошибка при генерации рекомендаций. Попробуйте еще раз.', 'error');
    } finally {
      setIsLoading(false);
    }
  };


  const getTotalItems = () => cart.reduce((sum, item) => sum + item.quantity, 0);

  // Определяем какие товары показывать
  const productsToShow = searchQuery ? filteredProducts : [];

  // Страница входа
  if (currentPage === 'login') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center p-4">
        {notification && (
          <Notification
            message={notification.message}
            type={notification.type}
            onClose={() => setNotification(null)}
          />
        )}

        <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="text-4xl mb-2">🛒</div>
            <h1 className="text-2xl font-bold text-gray-800">Smart Shop</h1>
            <p className="text-gray-600">Система персональных рекомендаций</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4 text-center">ВХОД В СИСТЕМУ</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email:
                </label>
                <input
                  type="email"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({...authForm, email: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="your@email.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Пароль:
                </label>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(e) => setAuthForm({...authForm, password: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Ваш пароль"
                />
              </div>

              <button
                onClick={handleLogin}
                disabled={isLoading}
                className="w-full bg-blue-500 hover:bg-blue-600 text-white py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isLoading ? 'Входим...' : 'ВОЙТИ'}
              </button>
            </div>

            <div className="text-center mt-4">
              <span className="text-sm text-gray-600">Нет аккаунта? </span>
              <button
                onClick={() => setCurrentPage('register')}
                className="text-blue-500 hover:text-blue-600 font-medium"
              >
                Регистрация
              </button>
            </div>

            <div className="mt-4 p-3 bg-blue-50 rounded text-xs text-gray-600">
              <strong>Тестовые учетные данные:</strong><br/>
              Email: user1@test.com<br/>
              Пароль: instacart123
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Страница регистрации
  if (currentPage === 'register') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-500 to-blue-600 flex items-center justify-center p-4">
        {notification && (
          <Notification
            message={notification.message}
            type={notification.type}
            onClose={() => setNotification(null)}
          />
        )}

        <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="text-4xl mb-2">🛒</div>
            <h1 className="text-2xl font-bold text-gray-800">Smart Shop</h1>
            <p className="text-gray-600">Создайте новый аккаунт</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4 text-center">РЕГИСТРАЦИЯ</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Имя:
                </label>
                <input
                  type="text"
                  value={authForm.name}
                  onChange={(e) => setAuthForm({...authForm, name: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="Ваше имя"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email:
                </label>
                <input
                  type="email"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({...authForm, email: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="your@email.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Пароль:
                </label>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(e) => setAuthForm({...authForm, password: e.target.value})}
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  placeholder="Минимум 6 символов"
                />
              </div>

              <button
                onClick={handleRegister}
                disabled={isLoading}
                className="w-full bg-green-500 hover:bg-green-600 text-white py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isLoading ? 'Регистрируем...' : 'ЗАРЕГИСТРИРОВАТЬСЯ'}
              </button>
            </div>

            <div className="text-center mt-4">
              <span className="text-sm text-gray-600">Уже есть аккаунт? </span>
              <button
                onClick={() => setCurrentPage('login')}
                className="text-green-500 hover:text-green-600 font-medium"
              >
                Войти
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Главная страница
  return (
    <div className="min-h-screen bg-gray-50">
      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onClose={() => setNotification(null)}
        />
      )}

      <OrderConfirmModal
        isOpen={orderConfirmModal.isOpen}
        orderData={orderConfirmModal.data}
        onClose={() => setOrderConfirmModal({ isOpen: false, data: null })}
      />

      {/* Заголовок */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <ShoppingCart className="w-6 h-6 text-blue-500" />
                <span className="text-xl font-bold text-gray-800">Smart Shop</span>
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Поиск товаров..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <User className="w-5 h-5 text-gray-600" />
                <span className="text-gray-700">{user?.name || 'Пользователь'}</span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-1 text-gray-600 hover:text-gray-800 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span>Выйти</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Основной контент */}
          <div className="lg:col-span-2 space-y-6">
            {/* Результаты поиска */}
            {searchQuery && (
              <section>
                <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                  РЕЗУЛЬТАТЫ ПОИСКА "{searchQuery}"
                  <div className="flex-1 h-px bg-gray-300 ml-4"></div>
                </h2>

                {filteredProducts.length > 0 ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {filteredProducts.map(product => (
                      <ProductCard
                        key={product.id}
                        product={product}
                        onAddToCart={addToCart}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">Товары не найдены</p>
                )}
              </section>
            )}

            {/* Рекомендации (показываем только если нет поиска) */}
            {!searchQuery && (
              <>
                {/* Показываем персональные рекомендации только если они есть */}
                {recommendations.length > 0 && (
                  <section>
                    <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                      РЕКОМЕНДАЦИИ ДЛЯ ВАС
                      <div className="flex-1 h-px bg-gray-300 ml-4"></div>
                    </h2>

                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                      {recommendations.slice(0, 10).map(product => (
                        <ProductCard
                          key={product.product_id}
                          product={{
                            id: product.product_id,
                            name: product.product_name,
                            aisle_name: product.aisle_name,
                            department_name: product.department_name
                          }}
                          onAddToCart={addToCart}
                        />
                      ))}
                    </div>
                  </section>
                )}

                {/* Сообщение и кнопка для пользователей с заказами но без рекомендаций */}
                {recommendations.length === 0 && userStats && userStats.monthlyOrders > 0 && (
                  <section>
                    <div className="bg-yellow-50 rounded-lg p-6 text-center">
                      <div className="text-4xl mb-3">🔄</div>
                      <h3 className="text-lg font-semibold mb-2">Обновите рекомендации</h3>
                      <p className="text-gray-600 mb-4">
                        У вас уже есть история заказов. Нажмите кнопку ниже, чтобы сгенерировать персональные рекомендации.
                      </p>
                      <button
                        onClick={generateRecommendations}
                        disabled={isLoading}
                        className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg font-medium transition-colors disabled:opacity-50"
                      >
                        {isLoading ? 'Генерируем...' : 'Сгенерировать рекомендации'}
                      </button>
                    </div>
                  </section>
                )}

                {/* Популярные товары */}
                <section>
                  <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                    {recommendations.length > 0 ? 'ПОПУЛЯРНЫЕ ТОВАРЫ' : 'РЕКОМЕНДУЕМЫЕ ТОВАРЫ'}
                    <div className="flex-1 h-px bg-gray-300 ml-4"></div>
                  </h2>

                  {popularProducts.length > 0 ? (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                      {popularProducts.slice(0, 10).map(product => (
                        <ProductCard
                          key={product.product_id || product.id}
                          product={{
                            id: product.product_id || product.id,
                            name: product.product_name || product.name,
                            aisle_name: product.aisle_name,
                            department_name: product.department_name
                          }}
                          onAddToCart={addToCart}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500">Загрузка товаров...</p>
                  )}
                </section>

                {/* Сообщение для новых пользователей */}
                {recommendations.length === 0 && userStats && userStats.monthlyOrders === 0 && (
                  <section>
                    <div className="bg-blue-50 rounded-lg p-6 text-center">
                      <div className="text-4xl mb-3">🎯</div>
                      <h3 className="text-lg font-semibold mb-2">Добро пожаловать в Smart Shop!</h3>
                      <p className="text-gray-600">
                        После вашего первого заказа здесь появятся персональные рекомендации,
                        подобранные специально для вас на основе ваших предпочтений.
                      </p>
                    </div>
                  </section>
                )}

                {/* Статистика пользователя */}
                {userStats && userStats.monthlyOrders > 0 && (
                  <section>
                    <div className="bg-white rounded-lg shadow-md p-6">
                      <h3 className="text-lg font-semibold mb-4 flex items-center">
                        📊 Ваша статистика
                      </h3>
                      <div className="space-y-2 text-sm text-gray-700">
                        <div>• Любимый отдел: {userStats.favoriteCategory}</div>
                        <div>• Всего заказов: {userStats.monthlyOrders}</div>
                        {userStats.frequentProducts && userStats.frequentProducts.length > 0 && (
                          <div>• Часто покупаете: {userStats.frequentProducts.join(', ')}</div>
                        )}
                      </div>
                    </div>
                  </section>
                )}
              </>
            )}
          </div>

          {/* Корзина */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-6 sticky top-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">МОЙ ЗАКАЗ</h3>
                <div className="flex-1 h-px bg-gray-300 ml-4"></div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <div className="flex items-center gap-2 mb-3">
                  <ShoppingCart className="w-5 h-5 text-gray-600" />
                  <span className="font-medium">
                    Текущий заказ ({getTotalItems()} товар{getTotalItems() !== 1 ? (getTotalItems() < 5 && getTotalItems() > 1 ? 'а' : 'ов') : ''})
                  </span>
                </div>

                {cart.length === 0 ? (
                  <p className="text-gray-500 text-sm">Корзина пуста</p>
                ) : (
                  <div className="space-y-2">
                    {cart.map(item => (
                      <CartItem
                        key={item.id}
                        item={item}
                        onUpdateQuantity={updateCartQuantity}
                        onRemove={removeFromCart}
                      />
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={submitOrder}
                  disabled={cart.length === 0 || isLoading}
                  className="flex-1 bg-green-500 hover:bg-green-600 text-white py-2 px-4 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? 'Оформляем...' : 'ОФОРМИТЬ ЗАКАЗ'}
                </button>
                <button
                  onClick={clearCart}
                  disabled={cart.length === 0}
                  className="bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ОЧИСТИТЬ
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SmartShop;