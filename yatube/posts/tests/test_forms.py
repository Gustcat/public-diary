import shutil
import tempfile

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from posts.forms import PostForm, CommentForm
from posts.models import Post, Group, Comment

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):
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
        cls.form = PostForm()
        cls.comment_form = CommentForm()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.author_client = Client()
        self.author_client.force_login(self.user)

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        posts_count = Post.objects.count()
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
        form_data = {
            'text': 'Новый текст',
            'group': self.group.id,
            'image': uploaded,
        }
        response = self.author_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, reverse('posts:profile',
                              kwargs={'username': self.user.username}))
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertTrue(
            Post.objects.filter(
                text=form_data['text'],
                group=self.group,
                image='posts/small.gif'
            ).exists()
        )

    def test_edit_post(self):
        """Валидная форма изменяет запись в Post."""
        self.other_group = Group.objects.create(
            title='т группа',
            slug='t-slug',
            description='Тестовое описание',
        )
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Измененный текст',
            'group': self.other_group.id,
        }
        response = self.author_client.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, reverse('posts:post_detail',
                              kwargs={'post_id': self.post.id}))
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                text=form_data['text'],
                group=self.other_group.id
            ).exists()
        )

    def test_create_comment(self):
        """Валидная форма создает запись в Comment."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Создан комментарий'
        }
        response = self.author_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, reverse('posts:post_detail',
                              kwargs={'post_id': self.post.id}))
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertTrue(
            Comment.objects.filter(
                text=form_data['text'],
            ).exists()
        )
