import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { Logger } from '@aicamera/shared';
import { ConfigService } from '@nestjs/config';
import { IoAdapter } from '@nestjs/platform-socket.io';

async function bootstrap() {
  const logger = Logger.create('WebSocket-Service');

  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  const port = configService.get('PORT', 3002);
  const nodeEnv = configService.get('NODE_ENV', 'development');

  // Configure WebSocket adapter
  app.useWebSocketAdapter(new IoAdapter(app));

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
      .setTitle('AI Camera WebSocket Service')
      .setDescription('WebSocket Microservice for real-time detection data')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    
    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('docs', app, document);
  }

  await app.listen(port);

  logger.info(`WebSocket Service started on port ${port}`);
  logger.info(`Environment: ${nodeEnv}`);
  logger.info(`Documentation: http://localhost:${port}/docs`);
}

bootstrap().catch((error) => {
  const logger = Logger.create('WebSocket-Service');
  logger.error('Failed to start WebSocket service', error);
  process.exit(1);
});