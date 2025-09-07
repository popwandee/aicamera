import { Controller, Get, Res } from '@nestjs/common';
import { Response } from 'express';
import { join } from 'path';

@Controller()
export class SpaController {
  // Match any path not starting with /api
  @Get(new RegExp('^(?!/api).*$'))
  handleSpa(@Res() res: Response) {
    const indexFilePath = join(process.cwd(), 'frontend', 'dist', 'index.html');
    res.sendFile(indexFilePath);
  }
}

