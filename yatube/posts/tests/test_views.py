import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.core.cache import cache

from posts.models import Post, Group, Follow

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост длинной больше 15 символов',
            group=cls.group,
            image=uploaded
        )
        cls.user2 = User.objects.create_user(username='auth2')
        cls.group2 = Group.objects.create(
            title='новая группа',
            slug='new-slug',
            description='описание новой группы',
        )
        cls.post2 = Post.objects.create(
            author=cls.user2,
            text='Новый пост',
            group=cls.group2
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}):
            'posts/group_list.html',
            reverse('posts:profile', kwargs={'username': 'auth'}):
            'posts/profile.html',
            reverse('posts:post_detail', kwargs={'post_id': self.post.id}):
            'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/post_create.html',
            reverse('posts:post_edit', kwargs={'post_id': self.post.id}):
            'posts/post_create.html'
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = (self.authorized_client.get(reverse(
            'posts:post_detail',
            kwargs={'post_id': self.post.id})))
        self.assertEqual(response.context.get('post').text,
                         'Тестовый пост длинной больше 15 символов')
        self.assertEqual(response.context.get('post').author.username,
                         'auth')
        self.assertEqual(response.context.get('post').group.title,
                         'Тестовая группа')
        self.assertEqual(response.context.get('post').image,
                         self.post.image)

    def test_create_page_show_correct_context(self):
        """Шаблон post_create сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_edit_page_show_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.id}))
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
            'image': forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        is_edit = response.context.get('is_edit')
        self.assertEqual(is_edit, True)
        post_id = response.context.get('post_id')
        self.assertEqual(post_id, self.post.id)

    def test_new_group_appears_in_right_pages(self):
        page_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group2.slug}),
            reverse('posts:profile', kwargs={'username': self.post2.author})
        ]
        for page_name in page_names:
            with self.subTest(page_name=page_name):
                response = self.authorized_client.get(page_name)
                posts = response.context['page_obj']
                self.assertIn(self.post2, posts)

    def test_group_list_does_not_contains_another_group(self):
        response_another_group = self.authorized_client.get(
            reverse('posts:group_list',
                    kwargs={'slug': PostPageTests.group.slug}))
        posts_another_group = response_another_group.context['page_obj']
        self.assertNotIn(self.post2, posts_another_group)

    def test_cache_contains_index_page(self):
        self.delete_post = Post.objects.create(
            author=self.user,
            text='Текст поста, который будет удален',
            group=self.group,
        )
        response_before = self.guest_client.get(reverse('posts:index'))
        content_before = response_before.content
        post = Post.objects.get(id=self.delete_post.id)
        post.delete()
        response_after = self.guest_client.get(reverse('posts:index'))
        content_after = response_after.content
        self.assertEqual(content_before, content_after)

    def test_authorized_client_can_follow(self):
        """Авторизованный пользователь может подписаться
        на другого пользователя"""
        self.authorized_client.get(reverse(
            'posts:profile_follow', kwargs={'username': self.user2.username}))
        follow = Follow.objects.filter(author=self.user2, user=self.user)
        self.assertTrue(follow.exists())

    def test_authorized_client_can_unfollow(self):
        """Авторизованный пользователь может отписаться
        от другого пользователя"""
        follow, _ = Follow.objects.get_or_create(author=self.user2,
                                                 user=self.user)
        self.authorized_client.get(reverse(
            'posts:profile_unfollow', kwargs={'username':
                                              self.user2.username}))
        follow = Follow.objects.filter(author=self.user2, user=self.user)
        self.assertFalse(follow.exists())

    def test_new_following_visible_only_in_follower_feed(self):
        """В ленте пользователя появляются только посты авторов,
        на которых подписан"""
        Follow.objects.create(
            author=self.user2,
            user=self.user
        )
        user3 = User.objects.create(username='auth3')
        client_without_follow = Client()
        client_without_follow.force_login(user3)
        post = Post.objects.create(
            author=self.user2,
            text='New post for follower'
        )
        response = self.authorized_client.get(reverse
                                              ('posts:follow_index'))
        posts = response.context['page_obj']
        self.assertIn(post, posts)
        response = client_without_follow.get(reverse
                                             ('posts:follow_index'))
        posts = response.context['page_obj']
        self.assertNotIn(post, posts)


class PostPaginatorTests(TestCase):
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
            group=cls.group
        )
        cls.user2 = User.objects.create_user(username='auth2')
        cls.group2 = Group.objects.create(
            title='Вторая группа',
            slug='second-slug',
            description='описание второй группы',
        )
        for i in range(12):
            cls.post = Post.objects.create(
                author=cls.user2,
                text=str(i),
                group=cls.group2
            )
        cls.page_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'second-slug'}),
            reverse('posts:profile', kwargs={'username': 'auth2'})
        ]

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_first_page_contains_ten_records(self):
        for page_name in PostPaginatorTests.page_names:
            with self.subTest(page_name=page_name):
                response = self.client.get(page_name)
                self.assertEqual(len(response.context['page_obj']), 10)

    def test_index_second_page_contains_three_records(self):
        response = self.authorized_client.get(reverse('posts:index')
                                              + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_profile_and_group_list_second_page_contains_three_records(self):
        for page_name in PostPaginatorTests.page_names:
            if page_name == reverse('posts:index'):
                continue
            with self.subTest(page_name=page_name):
                response = self.authorized_client.get(page_name + '?page=2')
                self.assertEqual(len(response.context['page_obj']), 2)


class PostFirstPostTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост длинной больше 15 символов',
            group=cls.group,
            image=uploaded
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_pages_with_multiple_posts_show_correct_context(self):
        """Шаблон index, group_list, profile
        сформирован с правильным контекстом."""
        page_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'auth'})
        ]
        for page_name in page_names:
            with self.subTest(page_name=page_name):
                response = self.authorized_client.get(page_name)
                first_object = response.context['page_obj'][0]
                task_text_0 = first_object.text
                task_author_0 = first_object.author.username
                task_group_0 = first_object.group.title
                task_image_0 = first_object.image
                self.assertEqual(task_text_0,
                                 'Тестовый пост длинной больше 15 символов')
                self.assertEqual(task_author_0, 'auth')
                self.assertEqual(task_group_0,
                                 'Тестовая группа')
                self.assertEqual(task_image_0,
                                 self.post.image)
                if page_name == reverse('posts:group_list',
                                        kwargs={'slug': 'test-slug'}):
                    self.assertEqual(first_object.group,
                                     response.context['group'])
                if page_name == reverse('posts:profile',
                                        kwargs={'username': 'auth'}):
                    self.assertEqual(first_object.author,
                                     response.context['author'])
