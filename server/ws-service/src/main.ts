import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

function checkBackendApiUrl() {
  const url = process.env.BACKEND_API_URL;
  if (!url) {
    console.warn(
      '[ws-service] BACKEND_API_URL is not set. Default http://localhost:3000 may cause 404. Set BACKEND_API_URL to include path, e.g. http://localhost:3000/server/api',
    );
    return;
  }
  const normalized = url.replace(/\/$/, '');
  if (!normalized.endsWith('/server/api')) {
    console.warn(
      `[ws-service] BACKEND_API_URL should end with /server/api (current: ${url}). Backend uses setGlobalPrefix('server/api').`,
    );
  }
}

async function bootstrap() {
  checkBackendApiUrl();
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  await app.listen(process.env.PORT ?? 3001);
}
bootstrap();
