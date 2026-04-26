import 'dotenv/config';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('server/api');
  app.use((req: any, res: any, next: any) => {
    if (req.path === '/' || req.path === '') {
      return res.redirect(302, '/server/');
    }
    next();
  });
  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();
