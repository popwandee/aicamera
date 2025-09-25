import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { Logger } from '@aicamera/shared';
import { ConfigService } from '@nestjs/config';

async function bootstrap() {
  const logger = Logger.create('File-Service');

  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  const port = configService.get('PORT', 3003);
  const nodeEnv = configService.get('NODE_ENV', 'development');

  // Global validation pipe
  app.useGlobalPipes(new ValidationPipe({
    transform: true,
    whitelist: true,
    forbidNonWhitelisted: true,
  }));

  // CORS configuration
  app.enableCors({
    origin: configService.get('CORS_ORIGINS', 'http://localhost:8080').split(','),
    credentials: true,
  });

  // Swagger documentation
  if (nodeEnv !== 'production') {
    const config = new DocumentBuilder()
      .setTitle('AI Camera File Service')
      .setDescription('File Management Microservice with SFTP and rsync support')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    
    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('docs', app, document);
  }

  await app.listen(port);

  logger.info(`File Service started on port ${port}`);
  logger.info(`Environment: ${nodeEnv}`);
  logger.info(`Documentation: http://localhost:${port}/docs`);
}

bootstrap().catch((error) => {
  const logger = Logger.create('File-Service');
  logger.error('Failed to start File service', error);
  process.exit(1);
});