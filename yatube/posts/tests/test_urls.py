from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from http import HTTPStatus

from posts.models import Post, Group

User = get_user_model()


class PostURLTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост длинной больше 15 символов',
        )
        cls.user2 = User.objects.create_user(username='auth2')

    def setUp(self):
        self.guest_client = Client()
        self.author_client = Client()
        self.author_client.force_login(self.user)
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user2)

    def test_answer_url_for_all_clients(self):
        """Страницы с правом доступа для всех доступны любому пользователю."""
        addresses = [
            '/',
            f'/group/{self.group.slug}/',
            f'/profile/{self.user.username}/',
            f'/posts/{self.post.id}/'
        ]
        for address in addresses:
            with self.subTest(address=address):
                response = self.guest_client.get(address)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_create_url_answer_authorized_clients(self):
        """Страница /create/ с правом доступа
        для авторизованного пользователя."""
        response = self.authorized_client.get('/create/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_create_url_redirect_guest_clients(self):
        """Страница /create/ перенаправляет анонимного пользователя."""
        response = self.guest_client.get('/create/', follow=True)
        self.assertRedirects(
            response, '/auth/login/?next=/create/'
        )

    def test_posts_edit_url_answer_author_client(self):
        """Страница /posts/<post_id>/edit с правом доступа для автора."""
        response = self.author_client.get(f'/posts/{self.post.id}/edit/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_posts_edit_url_redirect_client_not_author(self):
        """Страница /posts/<post_id>/edit перенаправляет не автора статьи."""
        clients = ['guest_client', 'authorized_client']
        for client in clients:
            with self.subTest(client=client):
                response = self.client.get(f'/posts/{self.post.id}/edit/',
                                           follow=True)
                self.assertRedirects(
                    response, f'/posts/{self.post.id}/'

                )

    def test_posts_comment_url_redirect_guest_client(self):
        """Страница /posts/<post_id>/comment перенаправляет
        анонимного пользователя  на регистрацию."""
        response = self.guest_client.get(f'/posts/{self.post.id}/comment/',
                                         follow=True)
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.id}/comment/'
        )

    def test_error_unexisting_page(self):
        """Несуществующая страница"""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @override_settings(DEBUG=False)
    def test_404_page(self):
        """При запросе несуществующей странице выдается 404.html"""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertTemplateUsed(response, 'core/404.html')
